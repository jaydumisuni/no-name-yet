#!/usr/bin/env python3
"""Apply the final static-review integration and false-positive correction.

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


def main() -> int:
    _patch_static_invariant()
    _patch_process_lock_detector()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
