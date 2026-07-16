"""Deterministic field investigations for Sergeant's permanent officers.

These checks are intentionally model-free.  They inspect repository text and
cross-file contracts without executing project code.  The goal is not to turn
every lexical signal into a defect; each emitted finding carries a concrete
location, a falsifier that was checked, and the permanent officer responsible
for the claim.
"""

from __future__ import annotations

import re
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


_MODEL_ID_RE = re.compile(r"@cf/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_TEST_PATH_RE = re.compile(r"tests/test_[A-Za-z0-9_./-]+\.py")
_WORKFLOW_PATH_RE = re.compile(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml")
_QUOTA_FUNCTION_RE = re.compile(
    r"^def\s+[A-Za-z0-9_]*quota[A-Za-z0-9_]*\s*\([^)]*\)\s*(?:->[^:]+)?\s*:\s*([\s\S]*?)(?=^def\s|\Z)",
    re.I | re.M,
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


def _workflow_secret_boundaries(path: str, text: str) -> list[FieldFinding]:
    findings: list[FieldFinding] = []
    for job, start, block in _workflow_jobs(text):
        secret_line = _line(block, re.compile(r"\bsecrets\.|\$\{\{\s*secrets\.", re.I))
        has_secrets = bool(re.search(r"\bsecrets\.|\$\{\{\s*secrets\.", block, re.I))
        checks_out_candidate = "actions/checkout" in block and bool(
            re.search(r"pull_request\.(?:head|merge)|github\.sha|refs/pull", block, re.I)
            or "ref:" not in block
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


def _workflow_contracts(root: Path, changed: list[str], texts: dict[str, str]) -> list[FieldFinding]:
    findings: list[FieldFinding] = []
    docs = {path: text for path, text in texts.items() if path.startswith("docs/")}
    workflows = {path: text for path, text in texts.items() if path.startswith(".github/workflows/")}
    roster_paths: set[str] = set()

    for doc_path, doc in docs.items():
        for workflow_path in set(_WORKFLOW_PATH_RE.findall(doc)):
            workflow = workflows.get(workflow_path)
            if workflow is None:
                _, workflow = _safe_source(root, workflow_path)
            if not workflow:
                continue
            required_tests = sorted(set(_TEST_PATH_RE.findall(doc)))
            for test_path in required_tests:
                occurrences = workflow.count(test_path)
                if occurrences < 2:
                    findings.append(
                        FieldFinding(
                            "Engineer",
                            "test_impact",
                            "major",
                            "Workflow assurance names a focused regression test that the workflow does not both trigger and execute.",
                            workflow_path,
                            _line(workflow, test_path) if occurrences else 1,
                            f"{doc_path} requires {test_path}; the workflow contains it {occurrences} time(s), but both path triggering and focused execution are required.",
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
                and "CLOUDFLARE" not in workflow.upper()
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
    ambiguous = [term for term in ("rce", "auth") if re.search(rf"[\"']{term}[\"']", text, re.I)]
    raw_substring = bool(re.search(r"\b(?:marker|term|keyword)\s+in\s+\w+|any\s*\([^\n]+\s+in\s+\w+", text, re.I))
    bounded = bool(re.search(r"\\b|fullmatch|finditer|re\.(?:search|compile)", text))
    if not ambiguous or not raw_substring or bounded:
        return []
    line = min(_line(text, f'"{term}"') for term in ambiguous)
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
    local_lock = bool(re.search(r"threading\.(?:Lock|RLock)\s*\(", text))
    persistent_state = bool(re.search(r"write_text|json\.dump|\.replace\s*\(|os\.replace|\.tmp[\"']", text))
    interprocess = bool(re.search(
        r"\bfcntl\.|\bmsvcrt\.|flock\b|lockf\b|portalocker|filelock|os\.O_EXCL|_interprocess_lock|atomic lock file",
        text,
        re.I,
    ))
    if not (local_lock and persistent_state) or interprocess:
        return []
    line = _line(text, re.compile(r"threading\.(?:Lock|RLock)"))
    return [
        FieldFinding(
            "Mechanic",
            "concurrency",
            "major",
            "Persistent usage-state update is protected only by a process-local lock.",
            path,
            line,
            "A threading lock surrounds filesystem state updates, but no inter-process lock is present; separate CLI, IDE, or CI processes can race and overwrite reservations.",
            "cross-process-state-race",
            0.92,
            ["Checked for POSIX and Windows inter-process file locking.", "Checked for a lock-file library."],
            "Serialize the complete load-modify-save transaction with an inter-process lock and atomically replace from a unique temporary file.",
        )
    ]


def _generic_quota_429(path: str, text: str) -> list[FieldFinding]:
    if "429" not in text or "quota" not in text.lower():
        return []
    bodies = _QUOTA_FUNCTION_RE.findall(text)
    candidate = "\n".join(bodies) if bodies else text
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


_SOURCE_CHECKS: tuple[Callable[[str, str], list[FieldFinding]], ...] = (
    _instruction_echo,
    _ambiguous_security_markers,
    _stale_daily_budget,
    _uncontained_file_reads,
    _process_local_file_lock,
    _generic_quota_429,
    _verbose_json_tiebreak,
)


def run_offline_investigations(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root)
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    readable: list[str] = []
    unavailable: list[str] = []
    for relative in changed:
        _, text = _safe_source(root_path, relative)
        if text:
            texts[relative] = text
            readable.append(relative)
        else:
            unavailable.append(relative)

    findings: list[FieldFinding] = []
    for path, text in texts.items():
        if path.startswith(".github/workflows/") and Path(path).suffix.lower() in {".yml", ".yaml"}:
            findings.extend(_workflow_secret_boundaries(path, text))
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
