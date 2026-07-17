#!/usr/bin/env python3
"""Apply the final static-review integrations and precision corrections.

This script is intentionally idempotent. It exists only to update large source
files without replacing their unrelated content through a blind whole-file edit.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _patch_static_invariant() -> None:
    path = ROOT / "main_review" / "static_invariant_review.py"
    text = path.read_text(encoding="utf-8")
    if "run_static_job_recovery_review" not in text:
        text = text.replace(
            "from .static_cross_path_review import run_static_cross_path_review\n"
            "from .static_status_review import run_static_status_review\n",
            "from .static_cross_path_review import run_static_cross_path_review\n"
            "from .static_job_recovery_review import run_static_job_recovery_review\n"
            "from .static_roundtrip_review import run_static_roundtrip_review\n"
            "from .static_status_review import run_static_status_review\n",
        )
    if "roundtrip_review = run_static_roundtrip_review" not in text:
        text = text.replace(
            "    status_review = run_static_status_review(root_path, changed)\n"
            "    findings.extend(dict(item) for item in status_review.get(\"findings\", []) if isinstance(item, dict))\n",
            "    status_review = run_static_status_review(root_path, changed)\n"
            "    findings.extend(dict(item) for item in status_review.get(\"findings\", []) if isinstance(item, dict))\n"
            "    roundtrip_review = run_static_roundtrip_review(root_path, changed)\n"
            "    findings.extend(dict(item) for item in roundtrip_review.get(\"findings\", []) if isinstance(item, dict))\n"
            "    job_recovery_review = run_static_job_recovery_review(root_path, changed)\n"
            "    findings.extend(dict(item) for item in job_recovery_review.get(\"findings\", []) if isinstance(item, dict))\n",
        )
    if '"static_roundtrip_review": roundtrip_review' not in text:
        text = text.replace(
            '        "static_status_review": status_review,\n',
            '        "static_status_review": status_review,\n'
            '        "static_roundtrip_review": roundtrip_review,\n'
            '        "static_job_recovery_review": job_recovery_review,\n',
        )
    required = (
        "run_static_job_recovery_review",
        "run_static_roundtrip_review",
        '"static_job_recovery_review": job_recovery_review',
    )
    if not all(marker in text for marker in required):
        raise RuntimeError("static invariant integration markers were not installed")
    path.write_text(text, encoding="utf-8")


def _patch_process_lock_detector() -> None:
    path = ROOT / "main_review" / "offline_investigation.py"
    text = path.read_text(encoding="utf-8")
    replacement = r'''def _process_local_file_lock(path: str, text: str) -> list[FieldFinding]:
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

'''
    pattern = re.compile(
        r"def _process_local_file_lock\(path: str, text: str\) -> list\[FieldFinding\]:\n"
        r"[\s\S]*?(?=def _generic_quota_429\()"
    )
    text, count = pattern.subn(lambda _: replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"expected one process-lock detector, replaced {count}")
    path.write_text(text, encoding="utf-8")


def _patch_executable_flow_admission() -> None:
    policy_path = ROOT / "main_review" / "capability_policy.py"
    policy = policy_path.read_text(encoding="utf-8")

    helper = r'''
def _matching_brace(text: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if character == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if character == "*" and following == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            index += 1
            continue
        if character == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if character == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if character in {"'", '"', "`"}:
            quote = character
            index += 1
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _brace_function_scopes(text: str) -> list[str]:
    header = re.compile(
        r"(?:"
        r"func\s*(?:\([^)]*\)\s*)?[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*(?:\([^)]*\)|[^\{\n]+)?|"
        r"(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\([^)]*\)|"
        r"(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"
        r")\s*\{",
        re.M,
    )
    scopes: list[str] = []
    for match in header.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            scopes.append(text[opening + 1:closing])
    return scopes


def _scope_has_input_to_sensitive_sink(scope: str) -> bool:
    sinks = list(DEMONSTRATED_SECURITY_SINK_RE.finditer(scope))
    if not sinks or not INPUT_SOURCE_RE.search(scope):
        return False

    assignments: list[tuple[str, int]] = []
    assignment_re = re.compile(
        r"(?m)^\s*(?:(?:const|let|var)\s+)?(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*"
        r"(?::=|=)\s*(?P<value>[^\n;]+)"
    )
    for match in assignment_re.finditer(scope):
        if INPUT_SOURCE_RE.search(match.group("value")):
            assignments.append((match.group("name"), match.end()))

    for sink in sinks:
        sink_region = scope[sink.start(): min(len(scope), sink.start() + 700)]
        if INPUT_SOURCE_RE.search(sink_region):
            return True
        for name, assignment_end in assignments:
            if assignment_end <= sink.start() and re.search(rf"\b{re.escape(name)}\b", sink_region):
                return True
    return False


def _has_local_executable_sensitive_flow(relative: str, text: str) -> bool:
    suffix = Path(relative).suffix.lower()
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        lines = text.splitlines(keepends=True)
        scopes = [
            "".join(lines[node.lineno - 1:(getattr(node, "end_lineno", None) or node.lineno)])
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    else:
        scopes = _brace_function_scopes(text)
    return any(_scope_has_input_to_sensitive_sink(scope) for scope in scopes)

'''
    if "def _has_local_executable_sensitive_flow" not in policy:
        marker = "\ndef _changed_test_covering_target("
        if marker not in policy:
            raise RuntimeError("capability-policy helper insertion marker missing")
        policy = policy.replace(marker, helper + marker, 1)

    flow_annotation = (
        "        if (\n"
        "            capability in {\"data_flow\", \"security_taint\"}\n"
        "            and text\n"
        "            and path\n"
        "            and _has_local_executable_sensitive_flow(path, text)\n"
        "        ):\n"
        "            finding[\"executable_flow_proof\"] = True\n"
        "            finding[\"direct_evidence\"] = True\n\n"
    )
    if 'finding["executable_flow_proof"] = True' not in policy:
        marker = "        if capability in IMPACT_ONLY_CAPABILITIES and severity in {\"blocker\", \"major\"}:\n"
        if marker not in policy:
            raise RuntimeError("capability-policy annotation insertion marker missing")
        policy = policy.replace(marker, flow_annotation + marker, 1)

    policy_path.write_text(policy, encoding="utf-8")

    council_path = ROOT / "main_review" / "officer_council.py"
    council = council_path.read_text(encoding="utf-8")
    old = (
        "        generic_risk = message in _GENERIC_RISK_MESSAGES or "
        "finding.get(\"admission_hint\") == \"risk_trigger\"\n"
    )
    new = (
        "        generic_risk = (\n"
        "            message in _GENERIC_RISK_MESSAGES\n"
        "            and not finding.get(\"executable_flow_proof\")\n"
        "        ) or finding.get(\"admission_hint\") == \"risk_trigger\"\n"
    )
    if old in council:
        council = council.replace(old, new, 1)
    if "and not finding.get(\"executable_flow_proof\")" not in council:
        raise RuntimeError("officer-council executable-flow admission marker missing")
    council_path.write_text(council, encoding="utf-8")


def main() -> int:
    _patch_static_invariant()
    _patch_process_lock_detector()
    _patch_executable_flow_admission()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
