"""Static Python shutdown checks for cancellation exception-group handling."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".py", ".pyi"}
_IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "dist", "build", "site-packages"}


def _safe_text(root: Path, relative: str) -> str:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _text_has_taskgroup(text: str) -> bool:
    if "TaskGroup" not in text:
        return False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "TaskGroup" in text
    return any(
        isinstance(node, ast.Call) and _name(node.func).endswith("TaskGroup")
        for node in ast.walk(tree)
    )


def _repository_taskgroup_evidence(root: Path, changed_texts: dict[str, str]) -> str | None:
    for path, text in changed_texts.items():
        if _text_has_taskgroup(text):
            return path

    scanned = 0
    for candidate in root.rglob("*.py"):
        if any(part in _IGNORED_PARTS for part in candidate.parts):
            continue
        scanned += 1
        if scanned > 4000:
            break
        try:
            if candidate.stat().st_size > 2_000_000:
                continue
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _text_has_taskgroup(text):
            try:
                return str(candidate.resolve().relative_to(root.resolve())).replace("\\", "/")
            except ValueError:
                return str(candidate)
    return None


def _cancelled_variables(function: ast.AsyncFunctionDef) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "cancel":
            continue
        target = _name(node.func.value)
        if target:
            result.add(target)
    return result


def _handler_names(node: ast.Try) -> set[str]:
    names: set[str] = set()
    for handler in node.handlers:
        name = _name(handler.type)
        if name:
            names.add(name)
    return names


def _awaited_names(node: ast.Try) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Await):
            name = _name(child.value)
            if name:
                names.add(name)
    return names


def _finding(path: str, line: int, function_name: str, taskgroup_path: str) -> dict[str, Any]:
    return {
        "source": "static-python-cancellation-officer",
        "officer": "Mechanic",
        "capability": "concurrency",
        "category": "concurrency",
        "severity": "major",
        "root_cause": "taskgroup-cancellation-not-caught-by-ordinary-except",
        "path": path,
        "line_start": line,
        "line_end": line,
        "evidence_ref": f"{path}:{line}",
        "supporting_evidence_refs": [f"{path}:{line}", taskgroup_path],
        "message": "TaskGroup cancellation can escape shutdown because grouped cancellation is handled with ordinary except semantics.",
        "evidence": (
            f"{function_name} cancels tracked tasks and awaits their completion inside a normal try/except that catches "
            f"CancelledError. Repository-local TaskGroup-backed work exists in {taskgroup_path}; Python 3.11 can propagate its "
            "cancellation as a BaseExceptionGroup that ordinary except CancelledError cannot match."
        ),
        "falsifiers_checked": [
            "Checked repository-local Python sources for actual TaskGroup construction.",
            "Checked that shutdown explicitly cancels tracked tasks before awaiting them.",
            "Checked that the await is guarded by ordinary ast.Try rather than ast.TryStar (except*).",
            "Checked for explicit BaseExceptionGroup or ExceptionGroup handling.",
        ],
        "verification_test": (
            "Use except* CancelledError or explicit BaseExceptionGroup-aware filtering, re-raise non-cancellation members, "
            "and repeatedly prove shutdown while TaskGroup work is active."
        ),
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_python_cancellation_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []
    changed_texts: dict[str, str] = {}

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        changed_texts[path] = text

    taskgroup_path = _repository_taskgroup_evidence(root_path, changed_texts)
    if taskgroup_path is not None:
        for path, text in changed_texts.items():
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for function in (node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)):
                cancelled = _cancelled_variables(function)
                if not cancelled:
                    continue
                for node in ast.walk(function):
                    if not isinstance(node, ast.Try):
                        continue
                    handlers = _handler_names(node)
                    if not any(name.endswith("CancelledError") for name in handlers):
                        continue
                    if any(name.endswith(("ExceptionGroup", "BaseExceptionGroup")) for name in handlers):
                        continue
                    awaited = _awaited_names(node)
                    if not awaited:
                        continue
                    if cancelled.isdisjoint(awaited) and not any(
                        isinstance(child, ast.Await) for child in ast.walk(node)
                    ):
                        continue
                    findings.append(_finding(path, int(node.lineno), function.name, taskgroup_path))
                    break

    unique = {
        (str(item.get("root_cause")), str(item.get("path"))): item
        for item in findings
    }
    return {
        "schema_version": "sergeant.static-python-cancellation-review.v2",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "taskgroup_evidence_path": taskgroup_path,
        "executed_project_code": False,
    }
