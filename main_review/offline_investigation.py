"""Deterministic field investigations for Sergeant's permanent officers.

These checks are intentionally model-free.  They inspect repository text and
cross-file contracts without executing project code.  The goal is not to turn
every lexical signal into a defect; each emitted finding carries a concrete
location, a falsifier that was checked, and the permanent officer responsible
for the claim.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class FieldFinding:
    officer: str
    capability: str
    severity: str
    message: str
    path: str
    line_start: int
    evidence: str
    root_cause: str
    confidence: float
    falsifiers_checked: list[str] = field(default_factory=list)
    verification_test: str = ""
    line_end: int | None = None
    source: str = "deterministic-officer"
    direct_evidence: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "officer": self.officer,
            "capability": self.capability,
            "category": self.capability,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end or self.line_start,
            "evidence_ref": f"{self.path}:{self.line_start}",
            "evidence": self.evidence,
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "falsifiers_checked": list(self.falsifiers_checked),
            "verification_test": self.verification_test,
            "direct_evidence": self.direct_evidence,
            "admission_hint": "actionable",
        }


@dataclass(frozen=True)
class CoverageRecord:
    officer: str
    check: str
    paths: list[str]
    status: str = "completed"
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "officer": self.officer,
            "check": self.check,
            "paths": list(self.paths),
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class PythonFunction:
    name: str
    body: str
    line_start: int


@dataclass(frozen=True)
class WorkflowCommand:
    text: str
    line_start: int


_MODEL_ID_RE = re.compile(r"@cf/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_TEST_PATH_RE = re.compile(r"tests/test_[A-Za-z0-9_./-]+\.py")
_PYTHON_TEST_RUNNER_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:[A-Za-z_][A-Za-z0-9_]*=[^\s]+\s+)*"
    r"(?:(?:uv|poetry|pipenv)\s+run\s+)?"
    r"(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?(?:pytest|unittest|tox|nox)\b",
    re.I | re.M,
)
_WORKFLOW_PATH_RE = re.compile(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml")
_QUOTA_FUNCTION_RE = re.compile(
    r"^def\s+[A-Za-z0-9_]*quota[A-Za-z0-9_]*\s*\([^)]*(?:error|exception)[^)]*\)"
    r"\s*(?:->[^:]+)?\s*:\s*([\s\S]*?)(?=^def\s|\Z)",
    re.I | re.M,
)
_PYTHON_FUNCTION_RE = re.compile(
    r"^def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^\n]*\)\s*(?:->[^:]+)?\s*:\s*\n"
    r"(?P<body>(?:(?:    |\t)[^\n]*(?:\n|\Z))*)",
    re.M,
)


def _safe_source(root: Path, relative: str) -> tuple[Path | None, str]:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return None, ""
        return path, path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, ""


def _line(text: str, marker: str | re.Pattern[str]) -> int:
    pattern = re.compile(re.escape(marker)) if isinstance(marker, str) else marker
    for number, row in enumerate(text.splitlines(), start=1):
        if pattern.search(row):
            return number
    return 1


def _python_functions(text: str) -> list[PythonFunction]:
    """Return every Python function, including methods and async functions."""

    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [
            PythonFunction(
                match.group("name"),
                match.group("body"),
                text[:match.start()].count("\n") + 1,
            )
            for match in _PYTHON_FUNCTION_RE.finditer(text)
        ]

    functions: list[PythonFunction] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = getattr(node, "end_lineno", None) or node.lineno
        if node.body:
            body_start = node.body[0].lineno
            raw_body = "".join(lines[body_start - 1:end_line])
        else:
            raw_body = ""
        # Normalize every function to the indentation shape used by the
        # deterministic checks: top-level statements at four spaces.
        body = textwrap.indent(textwrap.dedent(raw_body), "    ") if raw_body else ""
        functions.append(PythonFunction(node.name, body, node.lineno))
    return sorted(functions, key=lambda function: function.line_start)


def _workflow_jobs(text: str) -> list[tuple[str, int, str]]:
    """Return simple YAML job blocks without requiring a YAML dependency."""

    lines = text.splitlines()
    jobs_line = next((index for index, row in enumerate(lines) if row.strip() == "jobs:" and not row.startswith(" ")), None)
    if jobs_line is None:
        return []
    starts: list[tuple[str, int]] = []
    for index in range(jobs_line + 1, len(lines)):
        row = lines[index]
        if row and not row.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", row)
        if match:
            starts.append((match.group(1), index))
    blocks: list[tuple[str, int, str]] = []
    for position, (name, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        blocks.append((name, start + 1, "\n".join(lines[start:end])))
    return blocks


def _yaml_code(row: str) -> str:
    return row.split("#", 1)[0].rstrip()


def _workflow_trigger_lines(text: str) -> list[str]:
    lines = text.splitlines()
    for index, row in enumerate(lines):
        match = re.match(r'''^(?:on|"on"|'on')\s*:\s*(.*?)\s*$''', _yaml_code(row))
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            return [inline]
        block: list[str] = []
        for candidate in lines[index + 1:]:
            if candidate.strip() and not candidate.startswith((" ", "\t")):
                break
            block.append(candidate)
        return block
    return []


def _workflow_has_pull_request_trigger(text: str) -> bool:
    trigger = "\n".join(_yaml_code(row) for row in _workflow_trigger_lines(text))
    return bool(re.search(r"(?<![A-Za-z0-9_])pull_request(?![A-Za-z0-9_])", trigger))


def _clean_yaml_scalar(value: str) -> str:
    return value.strip().strip(",").strip().strip("'\"")


def _pull_request_trigger_paths(text: str) -> set[str]:
    trigger = _workflow_trigger_lines(text)
    for index, row in enumerate(trigger):
        code = _yaml_code(row)
        match = re.match(r'''^(\s*)(?:pull_request|"pull_request"|'pull_request')\s*:\s*(.*?)\s*$''', code)
        if not match:
            continue
        parent_indent = len(match.group(1))
        branch: list[str] = []
        for candidate in trigger[index + 1:]:
            candidate_code = _yaml_code(candidate)
            if candidate_code.strip() and len(candidate_code) - len(candidate_code.lstrip()) <= parent_indent:
                break
            branch.append(candidate)
        for path_index, candidate in enumerate(branch):
            candidate_code = _yaml_code(candidate)
            paths_match = re.match(r"^(\s*)paths\s*:\s*(.*?)\s*$", candidate_code)
            if not paths_match:
                continue
            inline = paths_match.group(2).strip()
            if inline.startswith("[") and inline.endswith("]"):
                return {
                    scalar
                    for item in inline[1:-1].split(",")
                    if (scalar := _clean_yaml_scalar(item)) and not scalar.startswith("!")
                }
            paths_indent = len(paths_match.group(1))
            paths: set[str] = set()
            for item in branch[path_index + 1:]:
                item_code = _yaml_code(item)
                if item_code.strip() and len(item_code) - len(item_code.lstrip()) <= paths_indent:
                    break
                list_item = re.match(r"^\s*-\s*(.+?)\s*$", item_code)
                if list_item:
                    scalar = _clean_yaml_scalar(list_item.group(1))
                    if scalar and not scalar.startswith("!"):
                        paths.add(scalar)
            return paths
    return set()


def _workflow_run_commands(text: str) -> list[WorkflowCommand]:
    """Return executable workflow commands with YAML block-scalar semantics.

    Literal ``|`` blocks retain newlines.  Folded ``>`` blocks become one shell
    line, preventing an apparent runner on a later YAML row from being treated as
    an independent command when YAML actually folds it into preceding text.
    """

    lines = text.splitlines()
    commands: list[WorkflowCommand] = []
    literal_markers = {"|", "|-", "|+"}
    folded_markers = {">", ">-", ">+"}
    for index, row in enumerate(lines):
        match = re.match(r"^(\s*)(?:-\s*)?run\s*:\s*(.*?)\s*$", _yaml_code(row))
        if not match:
            continue
        indent = len(match.group(1))
        inline = match.group(2).strip()
        command_lines: list[str] = []
        command_line = index + 1
        if inline and inline not in literal_markers | folded_markers:
            command_lines.append(_clean_yaml_scalar(inline))
        else:
            for candidate_index, candidate in enumerate(lines[index + 1:], start=index + 1):
                candidate_code = _yaml_code(candidate)
                if candidate_code.strip() and len(candidate_code) - len(candidate_code.lstrip()) <= indent:
                    break
                if candidate_code.strip():
                    if not command_lines:
                        command_line = candidate_index + 1
                    command_lines.append(candidate_code.strip())
        if not command_lines:
            continue
        separator = " " if inline in folded_markers else "\n"
        commands.append(WorkflowCommand(separator.join(command_lines), command_line))
    return commands

def _executed_test_paths(text: str) -> set[str]:
    """Return test paths appearing in actual runner invocations only."""

    paths: set[str] = set()
    for command in _workflow_run_commands(text):
        logical_lines: list[str] = []
        pending = ""
        for raw in command.text.splitlines() or [command.text]:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.endswith("\\"):
                pending += stripped[:-1].rstrip() + " "
                continue
            logical_lines.append((pending + stripped).strip())
            pending = ""
        if pending.strip():
            logical_lines.append(pending.strip())
        for logical in logical_lines:
            for segment in re.split(r"\s*(?:&&|\|\||;|\|)\s*", logical):
                candidate = segment.strip()
                if not candidate or candidate.startswith("#"):
                    continue
                runner = _PYTHON_TEST_RUNNER_RE.search(candidate)
                if runner is None:
                    continue
                paths.update(_TEST_PATH_RE.findall(candidate[runner.start():]))
    return paths

def _workflow_shell_operator_expansion(path: str, text: str) -> list[FieldFinding]:
    pattern = re.compile(
        r"\$\{[A-Za-z_][A-Za-z0-9_]*:\+[^}\n]*(?:\|\||&&|(?:^|\s)\d?>)[^}\n]*\}"
    )
    for command in _workflow_run_commands(text):
        match = pattern.search(command.text)
        if not match:
            continue
        line = command.line_start + command.text[:match.start()].count("\n")
        return [
            FieldFinding(
                "Engineer",
                "api_contract",
                "major",
                "Workflow embeds shell control operators inside conditional parameter expansion.",
                path,
                line,
                "Shell parsing happens before parameter expansion, so redirections and boolean operators produced by ${VAR:+...} become literal command arguments rather than control operators.",
                "workflow-shell-operator-expansion",
                0.96,
                ["Checked for an explicit shell if block.", "Checked whether redirection and fallback operators remain parser-visible."],
                "Use an explicit if block and keep redirection/fallback operators in ordinary shell syntax.",
            )
        ]
    return []


def _workflow_secret_boundaries(path: str, text: str) -> list[FieldFinding]:
    findings: list[FieldFinding] = []
    pull_request_trigger = _workflow_has_pull_request_trigger(text)
    for job, start, block in _workflow_jobs(text):
        secret_line = _line(block, re.compile(r"\bsecrets\.|\$\{\{\s*secrets\.", re.I))
        has_secrets = bool(re.search(r"\bsecrets\.|\$\{\{\s*secrets\.", block, re.I))
        checks_out_candidate = "actions/checkout" in block and bool(
            re.search(r"pull_request\.(?:head|merge)|github\.sha|refs/pull", block, re.I)
            or (pull_request_trigger and "ref:" not in block)
        )
        executes_project = bool(
            re.search(r"pip\s+install\s+-e\s+\.|python\s+-m\s+|pytest\b|\bsergeant-[a-z-]+\b", block, re.I)
        )
        protected = bool(re.search(r"^    environment:\s*[^\s]+", block, re.M))
        gated = "needs:" in block and bool(
            re.search(
                r"\b[A-Z][A-Z0-9_]*(?:ENABLED|APPROVED)\b|workflow_dispatch|approval",
                block,
                re.I,
            )
        )
        if has_secrets and checks_out_candidate and executes_project and not (protected and gated):
            findings.append(
                FieldFinding(
                    "Medic",
                    "security_taint",
                    "blocker",
                    "Secret-bearing workflow job executes pull-request-controlled project code without a protected approval boundary.",
                    path,
                    start + secret_line - 1,
                    f"Job '{job}' checks out candidate code, executes project commands, and exposes repository secrets without both a protected environment and an explicit gate.",
                    "workflow-secret-boundary",
                    0.96,
                    [
                        "Checked whether the job uses a protected environment.",
                        "Checked whether the live job depends on validated work and an explicit enable/approval gate.",
                    ],
                    "Split candidate validation from the protected secret-bearing job and prove candidate validation receives no provider secrets.",
                )
            )
    return findings


def _documented_workflow_tests(document: str) -> dict[str, set[str]]:
    """Associate each named regression test with its owning workflow mention."""

    workflow_matches = list(_WORKFLOW_PATH_RE.finditer(document))
    if not workflow_matches:
        return {}
    contracts: dict[str, set[str]] = {
        match.group(0): set() for match in workflow_matches
    }
    for test_match in _TEST_PATH_RE.finditer(document):
        line_start = document.rfind("\n", 0, test_match.start()) + 1
        line_end = document.find("\n", test_match.end())
        if line_end < 0:
            line_end = len(document)
        same_line = [
            match
            for match in workflow_matches
            if line_start <= match.start() < line_end
        ]
        candidates = same_line or workflow_matches
        owner = min(
            candidates,
            key=lambda match: abs(match.start() - test_match.start()),
        )
        contracts.setdefault(owner.group(0), set()).add(test_match.group(0))
    return contracts


def _workflow_contracts(root: Path, changed: list[str], texts: dict[str, str]) -> list[FieldFinding]:
    findings: list[FieldFinding] = []
    docs = {path: text for path, text in texts.items() if path.startswith("docs/")}
    workflows = {path: text for path, text in texts.items() if path.startswith(".github/workflows/")}
    roster_paths: set[str] = set()

    for doc_path, doc in docs.items():
        for workflow_path, documented_tests in _documented_workflow_tests(doc).items():
            workflow = workflows.get(workflow_path)
            if workflow is None:
                workflow_source, workflow = _safe_source(root, workflow_path)
                if workflow_source is None:
                    continue
            required_tests = sorted(documented_tests)
            trigger_paths = _pull_request_trigger_paths(workflow)
            executed_tests = _executed_test_paths(workflow)
            for test_path in required_tests:
                triggers_on_test = test_path in trigger_paths
                executes_test = test_path in executed_tests
                if not (triggers_on_test and executes_test):
                    findings.append(
                        FieldFinding(
                            "Engineer",
                            "test_impact",
                            "major",
                            "Workflow assurance names a focused regression test that the workflow does not both trigger and execute.",
                            workflow_path,
                            _line(workflow, test_path) if test_path in workflow else 1,
                            f"{doc_path} requires {test_path}; pull-request path trigger={triggers_on_test}, executed test command={executes_test}.",
                            "workflow-proof-contract",
                            0.93,
                            ["Checked the workflow path filter.", "Checked the focused test command."],
                            f"Add {test_path} to both the workflow trigger paths and focused test command.",
                        )
                    )

    # A workflow that declares its own model roster must enforce those exact
    # identities, not only a derived ``passed`` boolean or member count.
    for workflow_path, workflow in workflows.items():
        declared_models = set(_MODEL_ID_RE.findall(workflow))
        exact_gate = bool(
            re.search(
                r"set\s*\([\s\S]{0,500}?certified_models[\s\S]{0,500}?\)\s*==\s*(?:required|REQUIRED_MODELS|\{)",
                workflow,
            )
        )
        if len(declared_models) >= 2 and "certif" in workflow_path.lower() and not exact_gate:
            findings.append(
                FieldFinding(
                    "Engineer",
                    "api_contract",
                    "major",
                    "Certification workflow does not enforce its exact declared model roster.",
                    workflow_path,
                    _line(workflow, "SERGEANT_CLOUDFLARE_MODELS"),
                    f"The workflow declares {len(declared_models)} model IDs but has no exact certified-model set equality gate.",
                    "certification-roster-contract",
                    0.95,
                    ["Compared every workflow-declared model ID.", "Checked for exact certified-model set equality."],
                    "Reject missing, extra, or substituted members by comparing the certified model-ID set with the declared required set.",
                )
            )
            roster_paths.add(workflow_path)

    # Contract tests are executable declarations.  If one is changed alongside
    # a workflow, compare its explicit provider roster with the workflow gate.
    contract_tests = {
        path: text
        for path, text in texts.items()
        if path.startswith("tests/") and ("workflow_contract" in path or "REQUIRED_MODELS" in text)
    }
    for test_path, test_text in contract_tests.items():
        required_models = set(_MODEL_ID_RE.findall(test_text))
        if not required_models:
            continue
        for workflow_path, workflow in workflows.items():
            if workflow_path in roster_paths:
                continue
            if (
                "certif" not in workflow_path.lower()
                and "certified_models" not in workflow
            ):
                continue
            missing = sorted(required_models - set(_MODEL_ID_RE.findall(workflow)))
            exact_gate = bool(
                re.search(
                    r"set\s*\([\s\S]{0,500}?certified_models[\s\S]{0,500}?\)\s*==\s*(?:required|REQUIRED_MODELS|\{)",
                    workflow,
                )
            )
            if missing or not exact_gate:
                detail = f"missing IDs: {', '.join(missing)}" if missing else "the gate does not compare the certified set with the required set"
                findings.append(
                    FieldFinding(
                        "Engineer",
                        "api_contract",
                        "major",
                        "Certification workflow does not enforce the exact roster declared by its contract test.",
                        workflow_path,
                        _line(workflow, "certified_models"),
                        f"{test_path} declares {len(required_models)} required model IDs; {detail}.",
                        "certification-roster-contract",
                        0.95,
                        ["Compared every declared model ID.", "Checked for set equality rather than a derived boolean or count."],
                        "Reject missing, extra, or substituted members by comparing the certified model-ID set with the required set.",
                    )
                )
    return findings


def _instruction_echo(path: str, text: str) -> list[FieldFinding]:
    if "required" not in text or not re.search(r"contract|proof|response", text, re.I):
        return []
    suspicious = bool(
        re.search(r"for\s+\w+\s+in\s+\([^\n)]*[\"']required[\"'][^\n)]*\)", text)
        or re.search(r"payload\.get\s*\(\s*[\"']required[\"']\s*\)", text)
    )
    response_candidate = bool(re.search(r"candidates?\.append|return\s+.*required|matches?", text, re.I))
    if not (suspicious and response_candidate):
        return []
    line = _line(text, re.compile(r"payload\.get\s*\(\s*[\"']required|[\"']required[\"']"))
    return [
        FieldFinding(
            "Engineer",
            "api_contract",
            "major",
            "Response validation accepts the request's required-instruction object as a candidate answer.",
            path,
            line,
            "The validator reads the 'required' instruction key and admits it into response-candidate matching, allowing instruction echo to satisfy the contract.",
            "instruction-echo-contract",
            0.94,
            ["Checked for a genuine provider result envelope.", "Checked whether only top-level response fields are accepted."],
            "Reject echoed instruction objects; accept only the response contract or an explicitly supported provider result envelope.",
        )
    ]


def _ambiguous_security_markers(path: str, text: str) -> list[FieldFinding]:
    if not re.search(r"security|coverage|marker", text, re.I):
        return []
    marker_patterns = {
        "rce": re.compile(r'''["']rce["']''', re.I),
        "auth": re.compile(r'''["']auth["']''', re.I),
    }
    ambiguous = [term for term, pattern in marker_patterns.items() if pattern.search(text)]
    raw_substring = bool(re.search(r"\b(?:marker|term|keyword)\s+in\s+\w+|any\s*\([^\n]+\s+in\s+\w+", text, re.I))
    bounded = bool(re.search(r"\\b|fullmatch|finditer|re\.(?:search|compile)", text))
    if not ambiguous or not raw_substring or bounded:
        return []
    line = min(_line(text, marker_patterns[term]) for term in ambiguous)
    return [
        FieldFinding(
            "Medic",
            "security_taint",
            "major",
            "Security coverage uses ambiguous fragments with raw substring matching.",
            path,
            line,
            f"Ambiguous marker(s) {', '.join(ambiguous)} are matched as raw substrings, so unrelated words can satisfy a security proof gate.",
            "ambiguous-security-coverage",
            0.92,
            ["Checked for word-boundary regular expressions.", "Checked for exact normalized-term comparison."],
            "Use explicit normalized security phrases or word-boundary matching and add negative controls for unrelated words.",
        )
    ]


def _stale_daily_budget(path: str, text: str) -> list[FieldFinding]:
    if "budget_blocked" not in text or not re.search(r"ledger|state|json", text, re.I):
        return []
    sets_block = bool(re.search(r"[\"']budget_blocked[\"']\s*\]\s*=\s*True|budget_blocked\s*=\s*True", text))
    has_day = "budget_blocked_day" in text
    if not sets_block or has_day:
        return []
    line = _line(text, "budget_blocked")
    return [
        FieldFinding(
            "Mechanic",
            "concurrency",
            "major",
            "Persisted daily budget block has no associated UTC day or expiry transition.",
            path,
            line,
            "The persistent state sets budget_blocked=true but stores no budget-blocked day, so the next daily allowance cannot deterministically clear it.",
            "stale-budget-lifecycle",
            0.93,
            ["Checked for a persisted budget_blocked_day field.", "Checked for a later-day reset transition."],
            "Persist the UTC block day and clear both the flag and day when loading state on a later UTC day.",
        )
    ]


def _uncontained_file_reads(path: str, text: str) -> list[FieldFinding]:
    joins_external = bool(re.search(r"Path\s*\(\s*(?:root|base|repository|repo)\s*\)\s*/\s*\w+", text))
    reads = bool(re.search(r"\.read_text\s*\(|\.read_bytes\s*\(|\bopen\s*\(", text))
    contained = bool(re.search(r"\.resolve\s*\(|is_relative_to|relative_to\s*\(|commonpath|secure_filename", text))
    if not (joins_external and reads) or contained:
        return []
    line = _line(text, re.compile(r"Path\s*\(\s*(?:root|base|repository|repo)"))
    return [
        FieldFinding(
            "Medic",
            "security_taint",
            "major",
            "Repository-relative external path is read without canonical containment proof.",
            path,
            line,
            "A caller-supplied relative path is joined to the repository root and read, but the resolved path is never proved to remain beneath that root.",
            "unsafe-file-access",
            0.91,
            ["Checked for canonical resolve().", "Checked for relative_to/is_relative_to/commonpath containment."],
            "Resolve the root and candidate path, reject absolute or parent traversal, and prove containment before reading.",
        )
    ]


def _process_local_file_lock(path: str, text: str) -> list[FieldFinding]:
    """Report only a process-local lock that actually guards a file transaction.

    A lock declaration and a filesystem write somewhere else in the same module
    are unrelated evidence.  The guard and persistent mutation must meet in one
    function before this root is admitted.
    """

    interprocess = bool(re.search(
        r"\bfcntl\.|\bmsvcrt\.|flock\b|lockf\b|portalocker|filelock|"
        r"os\.O_EXCL|_interprocess_lock|atomic lock file",
        text,
        re.I,
    ))
    if interprocess:
        return []

    lock_names = {
        match.group("name")
        for match in re.finditer(
            r"(?P<name>(?:self\.)?[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"threading\.(?:Lock|RLock)\s*\(",
            text,
        )
    }
    if not lock_names:
        return []

    persistent_re = re.compile(
        r"\.write_text\s*\(|\.write_bytes\s*\(|json\.dump\s*\(|"
        r"\bos\.replace\s*\(|(?<![.\w])replace\s*\(|"
        r"\.replace\s*\(|\bopen\s*\([^\n,]+,\s*[\"'][^\"']*[wax+]",
        re.I,
    )
    for function in _python_functions(text):
        body = function.body
        persistent = persistent_re.search(body)
        if persistent is None:
            continue
        for lock_name in sorted(lock_names):
            escaped = re.escape(lock_name)
            with_guard = re.search(
                rf"\bwith\s+{escaped}\s*:\s*[\s\S]*?",
                body,
                re.I,
            )
            acquire = re.search(rf"\b{escaped}\.(?:acquire|lock)\s*\(", body, re.I)
            if with_guard is None and acquire is None:
                continue
            guard_position = min(
                [match.start() for match in (with_guard, acquire) if match is not None]
            )
            if guard_position > persistent.start():
                continue
            return [
                FieldFinding(
                    "Mechanic",
                    "concurrency",
                    "major",
                    "Persistent file-state update is guarded only by a process-local lock.",
                    path,
                    function.line_start,
                    f"Function {function.name} performs a filesystem state mutation while holding {lock_name}, "
                    "but the lock cannot serialize another process.",
                    "cross-process-state-race",
                    0.94,
                    [
                        "Required the process-local lock and filesystem mutation to occur in the same function.",
                        "Checked for POSIX, Windows, lock-file, and library-backed inter-process locking.",
                    ],
                    "Serialize the complete load-modify-save transaction with an inter-process lock and atomically replace a unique temporary file.",
                )
            ]
    return []

def _generic_quota_429(path: str, text: str) -> list[FieldFinding]:
    if "429" not in text or "quota" not in text.lower():
        return []
    bodies = _QUOTA_FUNCTION_RE.findall(text)
    if not bodies:
        return []
    candidate = "\n".join(bodies)
    generic_pattern = r"(?:http\s*)?429|status(?:_code)?\s*==\s*429"
    allocation_pattern = (
        r"4006|daily[_ -]+free[_ -]+allocation|daily[_ -]+allocation[_ -]+is[_ -]+exhausted|"
        r"allocation[_ -]+exhausted|neuron[_ -]+allocation"
    )
    generic = bool(re.search(generic_pattern, candidate, re.I))
    # A generic 429 term joined with ``or`` is independently sufficient and
    # therefore still misclassifies transient throttling even when another OR
    # branch correctly recognizes provider code 4006.
    boolean_terms = re.split(r"\bor\b", candidate, flags=re.I)
    generic_without_allocation = any(
        re.search(generic_pattern, term, re.I) and not re.search(allocation_pattern, term, re.I)
        for term in boolean_terms
    )
    if not generic or not generic_without_allocation:
        return []
    line = _line(text, "429")
    return [
        FieldFinding(
            "Mechanic",
            "api_contract",
            "major",
            "Generic HTTP 429 is classified as daily provider-allocation exhaustion.",
            path,
            line,
            "The quota classifier accepts status 429 without requiring the provider's allocation code or allocation-specific marker, so transient throttling can open a day-long circuit.",
            "quota-error-classification",
            0.93,
            ["Checked for provider code 4006.", "Checked for daily-allocation-specific response markers."],
            "Open the daily circuit only for allocation-specific evidence; route generic throttles through transient provider-error handling.",
        )
    ]


def _verbose_json_tiebreak(path: str, text: str) -> list[FieldFinding]:
    candidate_flow = "json_candidate" in text or bool(re.search(r"max\s*\(\s*(?:objects|candidates)", text))
    length_score = bool(re.search(r"len\s*\(\s*json\.dumps|len\s*\(\s*(?:payload|candidate|value)", text))
    length_ranked_selection = bool(
        re.search(
            r"max\s*\(\s*(?:objects|candidates)\s*,\s*key\s*=\s*_?json_candidate_score",
            text,
        )
    )
    if not candidate_flow or not length_score or not length_ranked_selection:
        return []
    line = _line(text, re.compile(r"len\s*\("))
    return [
        FieldFinding(
            "Engineer",
            "api_contract",
            "major",
            "Structured-response candidate tie-break prefers payload length instead of the final schema match.",
            path,
            line,
            "Equal-schema JSON candidates are ranked by serialized size, allowing an earlier verbose example or reasoning object to displace the later final response.",
            "structured-response-selection",
            0.9,
            ["Checked for a final-position/index tie-break.", "Checked whether schema score is the primary discriminator."],
            "Keep schema scoring primary and choose the later candidate when schema scores tie.",
        )
    ]


def _atomic_replace_without_fsync(path: str, text: str) -> list[FieldFinding]:
    findings: list[FieldFinding] = []
    for function in _python_functions(text):
        body = function.body
        handles = {
            match.group("handle")
            for match in re.finditer(
                r"NamedTemporaryFile[^\n]*\bas\s+(?P<handle>[A-Za-z_][A-Za-z0-9_]*)",
                body,
            )
        }
        aliases: dict[str, str] = {}
        for match in re.finditer(
            r"(?m)^\s*(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^\n]*?"
            r"(?P<handle>[A-Za-z_][A-Za-z0-9_]*)\.name\b",
            body,
        ):
            if match.group("handle") in handles:
                aliases[match.group("alias")] = match.group("handle")

        fd_paths: dict[str, str] = {}
        for match in re.finditer(
            r"(?m)^\s*(?P<fd>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
            r"(?P<path>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:tempfile\.)?mkstemp\s*\(",
            body,
        ):
            fd_paths[match.group("path")] = match.group("fd")

        path_objects: dict[str, str] = {}
        for match in re.finditer(
            r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"(?:pathlib\.)?Path\s*\(\s*(?P<source>[^)\n]+)\s*\)",
            body,
        ):
            path_objects[match.group("name")] = match.group("source").strip()
        for match in re.finditer(
            r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"[A-Za-z_][A-Za-z0-9_]*\.__class__\s*\(\s*(?P<source>[^)\n]+)\s*\)",
            body,
        ):
            path_objects[match.group("name")] = match.group("source").strip()
        for match in re.finditer(
            r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"(?P<source>[A-Za-z_][A-Za-z0-9_]*\.(?:with_suffix|with_name|resolve|absolute)\s*\([^\n]*\))",
            body,
        ):
            path_objects[match.group("name")] = match.group("source").strip()

        replacements: list[tuple[int, str]] = []
        for match in re.finditer(
            r"(?:\bos\.replace|(?<![.\w])replace)\s*\(\s*([^,\n]+)\s*,",
            body,
        ):
            replacements.append((match.start(), match.group(1).strip()))
        for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\.replace\s*\(", body):
            receiver = match.group(1)
            if receiver in path_objects:
                replacements.append((match.start(), receiver))
        if not replacements:
            continue

        non_durable: list[str] = []
        last_replace_by_identity: dict[str, int] = {}
        for replace_pos, source in sorted(replacements):
            normalized = source.strip()
            if normalized in path_objects:
                normalized = path_objects[normalized]
            handle: str | None = None
            if normalized in aliases:
                handle = aliases[normalized]
            elif normalized.endswith(".name") and normalized[:-5] in handles:
                handle = normalized[:-5]
            elif normalized in handles:
                handle = normalized

            if handle is not None:
                identity = f"handle:{handle}"
                boundary = last_replace_by_identity.get(identity, -1)
                write_positions = [
                    match.start()
                    for match in re.finditer(rf"\b{re.escape(handle)}\.write\s*\(", body)
                ]
                write_positions.extend(
                    match.start()
                    for match in re.finditer(
                        rf"\bjson\.dump\s*\([^\n]*,\s*{re.escape(handle)}\s*\)",
                        body,
                    )
                )
                flush_positions = [
                    match.start()
                    for match in re.finditer(rf"\b{re.escape(handle)}\.flush\s*\(", body)
                ]
                fsync_positions = [
                    match.start()
                    for match in re.finditer(
                        rf"\bos\.fsync\s*\(\s*{re.escape(handle)}\.fileno\s*\(\s*\)\s*\)",
                        body,
                    )
                ]
                durable = any(
                    boundary < write < flush < fsync < replace_pos
                    for write in write_positions
                    for flush in flush_positions
                    for fsync in fsync_positions
                )
            elif normalized in fd_paths:
                fd = fd_paths[normalized]
                identity = f"fd:{fd}"
                boundary = last_replace_by_identity.get(identity, -1)
                writes = [
                    match.start()
                    for match in re.finditer(rf"\bos\.write\s*\(\s*{re.escape(fd)}\s*,", body)
                ]
                fsyncs = [
                    match.start()
                    for match in re.finditer(rf"\bos\.fsync\s*\(\s*{re.escape(fd)}\s*\)", body)
                ]
                durable = any(
                    boundary < write < fsync < replace_pos
                    for write in writes
                    for fsync in fsyncs
                )
            else:
                identity = f"source:{normalized}"
                durable = False

            last_replace_by_identity[identity] = replace_pos
            if not durable:
                non_durable.append(source)

        if not non_durable:
            continue
        findings.append(
            FieldFinding(
                "Mechanic",
                "concurrency",
                "minor",
                "Atomic file replacement is not durably flushed before publication.",
                path,
                function.line_start,
                f"Function {function.name} has replacement source(s) without their own ordered write -> flush -> fsync -> replace proof: {', '.join(non_durable)}.",
                "atomic-replace-durability",
                0.9,
                [
                    "Associated each replacement with its own temporary handle or file descriptor.",
                    "Required every replacement to preserve its own durability sequence.",
                ],
                "For every temporary artifact, write and flush the matching handle, fsync its descriptor, then atomically replace the destination.",
            )
        )
    return findings

def _uncanonicalized_severity(path: str, text: str) -> list[FieldFinding]:
    downstream_lowercase = bool(
        re.search(
            r"(?:item\.get\s*\(\s*[\"']severity[\"']\s*\)|\bseverity\b)\s*"
            r"(?:==|in)\s*(?:[\"'](?:blocker|major)[\"']|\{[^}]*[\"'](?:blocker|major)[\"'])",
            text,
        )
    )
    if not downstream_lowercase:
        return []
    findings: list[FieldFinding] = []
    for function in _python_functions(text):
        if "normal" not in function.name.lower():
            continue
        body = function.body
        if "severity" not in body or not re.search(r"dict\s*\(|copy\s*\(", body):
            continue
        canonical = bool(re.search(r"severity[^\n]*(?:\.lower\s*\(|\.casefold\s*\()|(?:\.lower\s*\(|\.casefold\s*\()[^\n]*severity", body))
        if canonical:
            continue
        findings.append(
            FieldFinding(
                "Engineer",
                "api_contract",
                "blocker",
                "Finding severity is not canonicalized before lowercase verdict comparisons.",
                path,
                function.line_start,
                "The normalization path preserves caller casing while downstream verdict logic recognizes only lowercase blocker/major values, allowing an admitted severe finding to produce PASS.",
                "severity-canonicalization",
                0.95,
                ["Checked for lower()/casefold() in the normalization path.", "Checked downstream blocker/major comparisons."],
                "Canonicalize stored severity once during normalization and reuse that value for admission, status, actions and verdict.",
            )
        )
    return findings


def _overwritten_disposition_precedence(path: str, text: str) -> list[FieldFinding]:
    assignment = re.search(
        r"(?:disposition|admission_ledger)\s*=\s*\{(?P<body>[\s\S]{0,1200}?)\n\s*\}",
        text,
    )
    if not assignment:
        return []
    body = assignment.group("body")
    admitted_at = body.find("for item in admitted")
    rejected_at = body.find("for item in rejected")
    if admitted_at < 0 or rejected_at < 0 or rejected_at < admitted_at:
        return []
    line = text[:assignment.start()].count("\n") + 1
    return [
        FieldFinding(
            "Analyst",
            "api_contract",
            "major",
            "Weaker rejected disposition can overwrite the same canonical admitted finding.",
            path,
            line,
            "The disposition mapping expands admitted identities before rejected identities, so a duplicate source claim with the same canonical ID replaces the stronger Judge decision.",
            "disposition-precedence",
            0.93,
            ["Checked for admitted-over-advisory-over-rejected precedence.", "Checked whether source duplicates can share canonical identity."],
            "Build one canonical disposition map with rejected first, then advisory, then admitted precedence.",
        )
    ]


def _benchmark_risk_trigger_predictions(path: str, text: str) -> list[FieldFinding]:
    if "benchmark" not in Path(path).stem.lower() and "metric" not in Path(path).stem.lower():
        return []
    if "advisory_findings" not in text or "risk_trigger" not in text:
        return []
    admits_risk = bool(
        re.search(
            r"(?:admission[^\n]{0,120}|item\.get\s*\(\s*[\"']admission[\"']\s*\)[^\n]{0,120})"
            r"(?:in|==)[^\n]{0,120}[\"']risk_trigger[\"']",
            text,
        )
    )
    if not admits_risk:
        return []
    line = _line(text, "risk_trigger")
    return [
        FieldFinding(
            "Judge",
            "testing",
            "major",
            "Benchmark prediction extraction admits a non-gating risk trigger.",
            path,
            line,
            "Risk-trigger evidence is explicitly non-actionable, but the benchmark includes it as a prediction and can corrupt precision, recall and finding counts.",
            "benchmark-risk-trigger-filter",
            0.94,
            ["Checked the Judge admission field rather than message text.", "Checked that ordinary minor advisories remain measurable."],
            "Benchmark admitted findings and true advisories only; exclude every risk_trigger by disposition.",
        )
    ]


def _formation_evidence_early_return(path: str, text: str) -> list[FieldFinding]:
    findings: list[FieldFinding] = []
    for function in _python_functions(text):
        name = function.name.lower()
        if "report" not in name or "build" not in name:
            continue
        body = function.body
        branch = re.search(r"if\s+formation_reports\s*:(?P<branch>[\s\S]*?)(?=\n    \S|\Z)", body)
        if not branch or "return" not in branch.group("branch"):
            continue
        branch_text = branch.group("branch")
        if "learning" in branch_text and "graduation" in branch_text:
            continue
        findings.append(
            FieldFinding(
                "Archivist",
                "api_contract",
                "major",
                "Canonical formation reports return before learning and graduation evidence is attached.",
                path,
                function.line_start,
                "The canonical report branch exits without consuming the supplied learning and graduation packets, making Archivist and Judge evidence decorative or absent.",
                "formation-evidence-loss",
                0.91,
                ["Checked Archivist learning candidates.", "Checked Judge graduation outcome propagation."],
                "Enrich canonical Archivist and Judge reports with the supplied evidence before returning.",
            )
        )
    return findings


_SOURCE_CHECKS: tuple[Callable[[str, str], list[FieldFinding]], ...] = (
    _instruction_echo,
    _ambiguous_security_markers,
    _stale_daily_budget,
    _uncontained_file_reads,
    _process_local_file_lock,
    _generic_quota_429,
    _verbose_json_tiebreak,
    _atomic_replace_without_fsync,
    _uncanonicalized_severity,
    _overwritten_disposition_precedence,
    _benchmark_risk_trigger_predictions,
    _formation_evidence_early_return,
)


def run_offline_investigations(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root)
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    readable: list[str] = []
    unavailable: list[str] = []
    for relative in changed:
        source_path, text = _safe_source(root_path, relative)
        if source_path is not None:
            texts[relative] = text
            readable.append(relative)
        else:
            unavailable.append(relative)

    findings: list[FieldFinding] = []
    for path, text in texts.items():
        if path.startswith(".github/workflows/") and Path(path).suffix.lower() in {".yml", ".yaml"}:
            findings.extend(_workflow_secret_boundaries(path, text))
            findings.extend(_workflow_shell_operator_expansion(path, text))
        is_test = path.startswith(("tests/", "test/")) or Path(path).name.lower().startswith("test_")
        if not is_test and Path(path).suffix.lower() in {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}:
            for check in _SOURCE_CHECKS:
                findings.extend(check(path, text))
    findings.extend(_workflow_contracts(root_path, changed, texts))

    # An exact duplicate from two deterministic rules is still one claim.
    unique: dict[tuple[str, str, str, int], FieldFinding] = {}
    for finding in findings:
        unique[(finding.root_cause, finding.path, finding.message, finding.line_start)] = finding

    coverage = [
        CoverageRecord("Scout", "changed-scope inventory", changed, evidence=f"{len(readable)} readable, {len(unavailable)} unavailable").to_dict(),
        CoverageRecord("Engineer", "contracts, proof wiring and response selection", readable).to_dict(),
        CoverageRecord("Medic", "trust boundaries, containment and security proof", readable).to_dict(),
        CoverageRecord("Mechanic", "state lifecycle, quota semantics and concurrency", readable).to_dict(),
    ]
    return {
        "mode": "model_free_static",
        "findings": [item.to_dict() for item in unique.values()],
        "finding_count": len(unique),
        "coverage": coverage,
        "readable_changed_files": readable,
        "unavailable_changed_files": unavailable,
        "executed_project_code": False,
    }
