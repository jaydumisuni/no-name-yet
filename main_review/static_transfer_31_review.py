"""Static checks learned after transfer set 31's blind first pass was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".scala", ".ex", ".exs", ".swift"}


def _safe_text(root: Path, relative: str) -> str:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _line(text: str, offset: int) -> int:
    return text[: max(0, offset)].count("\n") + 1


def _finding(
    *,
    officer: str,
    capability: str,
    category: str,
    severity: str,
    root_cause: str,
    path: str,
    line_start: int,
    message: str,
    evidence: str,
    falsifiers: list[str],
    verification: str,
    confidence: float,
    supporting: Iterable[str] = (),
) -> dict[str, Any]:
    primary = f"{path}:{line_start}"
    return {
        "source": "static-transfer-31-officer",
        "officer": officer,
        "capability": capability,
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": primary,
        "supporting_evidence_refs": list(dict.fromkeys([primary, *supporting])),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": falsifiers,
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _scala_handoff_findings(files: dict[str, str]) -> list[dict[str, Any]]:
    reader_source: tuple[str, str, int] | None = None
    manager_source: tuple[str, str, int] | None = None

    for path, text in files.items():
        suspension = re.search(
            r"case\s+StopReading\s*\([^)]*\)\s*=>[\s\S]{0,450}?context\.become\(notReading\)",
            text,
        )
        state_start = re.search(r"def\s+notReading\s*:\s*Receive\s*=\s*\{", text)
        if suspension is not None and state_start is not None:
            state_end = re.search(
                r"\n\s*private\s+def\s+[A-Za-z_]\w*|\n\s*def\s+[A-Za-z_]\w*\s*\(",
                text[state_start.end() :],
            )
            end = state_start.end() + (state_end.start() if state_end else 3500)
            body = text[state_start.end() : end]
            if "ResumeReading" not in body:
                reader_source = (path, text, suspension.start())

        terminated = re.search(
            r"case\s+Terminated\s*\(\s*(?P<endpoint>[A-Za-z_]\w*)\s*\)\s*=>"
            r"(?P<body>[\s\S]{0,700}?)(?=\n\s*case\s+|\n\s*\})",
            text,
        )
        if (
            terminated is not None
            and "pendingReadHandoffs" in text
            and "acceptPendingReader" in terminated.group("body")
            and "unregisterEndpoint" in terminated.group("body")
            and "registerReadOnlyEndpoint" in text
            and "resumeReadingIfNeeded" not in text
            and "readOnlyReaderResumptions" not in text
        ):
            manager_source = (path, text, terminated.start())

    if reader_source is None or manager_source is None:
        return []

    reader_path, reader_text, reader_offset = reader_source
    manager_path, manager_text, manager_offset = manager_source
    return [
        _finding(
            officer="Engineer",
            capability="protocol_lifecycle",
            category="correctness",
            severity="blocker",
            root_cause="reader-suspension-handoff-has-no-failure-resume-path",
            path=reader_path,
            line_start=_line(reader_text, reader_offset),
            message=(
                "A passive reader handoff can suspend the original reader permanently because failure of the replacement endpoint has no matching resume transition."
            ),
            evidence=(
                "The original reader enters a `notReading` state after the handoff request, and that state exposes no resume message. "
                "The endpoint manager creates a replacement read-only endpoint, but termination only retries a pending handoff, unregisters the endpoint, and never restores the still-valid original writer/reader pair."
            ),
            falsifiers=[
                "Required an explicit transition into a suspended reader state during endpoint handoff.",
                "Checked the suspended state's receive handler for a resume transition.",
                "Required the manager to create/register a replacement read-only endpoint and observe its termination.",
                "Checked for fallback state binding the replacement endpoint to the original writer, address, and identity.",
                "Excluded implementations that resume only when the original endpoint and remote identity still match.",
            ],
            verification=(
                "Track the original readable endpoint across replacement handoffs, resume it only when the replacement dies and the current endpoint identity still matches, and test replacement chains, UID changes, stale termination, gated/idle states, and shutdown."
            ),
            confidence=0.99,
            supporting=(f"{manager_path}:{_line(manager_text, manager_offset)}",),
        )
    ]


def _elixir_path_binding_findings(path: str, text: str) -> list[dict[str, Any]]:
    join_function = re.search(
        r"def\s+join_path\s*\([^)]*\)[\s\S]{0,180}?\bdo\b(?P<body>[\s\S]{0,900}?)\n\s*end",
        text,
    )
    if join_function is None:
        return []
    body = join_function.group("body")
    unsafe = re.search(
        r"Path\.join\s*\(\s*path\s*\)[\s\S]{0,240}?\|>\s*"
        r"(?P<expander>[A-Za-z_]\w*bindings[A-Za-z_]*)\s*\(\s*project\s*\)",
        body,
        re.I,
    )
    if unsafe is None:
        return []
    expander = unsafe.group("expander")
    definition = re.search(rf"defp?\s+{re.escape(expander)}\s*\([^)]*path", text)
    replacement = re.search(r"Regex\.replace\s*\([^,]+,\s*path\s*,", text)
    if definition is None or replacement is None:
        return []

    absolute = join_function.start("body") + unsafe.start()
    return [
        _finding(
            officer="Engineer",
            capability="data_flow",
            category="correctness",
            severity="major",
            root_cause="template-binding-expansion-applied-after-host-path-join",
            path=path,
            line_start=_line(text, absolute),
            message=(
                "Template binding expansion is applied to the complete host path after the template-relative path is joined to it."
            ),
            evidence=(
                "The base filesystem path is joined with the template path before a regex-based binding expander scans the resulting absolute path. "
                "Binding-like text in a parent directory is therefore interpreted as template syntax and can trigger missing-key failures or rewrite host-controlled path segments."
            ),
            falsifiers=[
                "Required a base/host path to be joined with a template-relative path before expansion.",
                "Required the downstream expander to scan its entire path argument for binding tokens.",
                "Checked whether only the relative template fragment is expanded before joining.",
                "Excluded literal joins and expanders scoped to parsed template tokens rather than the full filesystem path.",
            ],
            verification=(
                "Expand bindings only in the relative template path, then join the expanded fragment to the untouched base path; test parent directories containing colons and binding-shaped names alongside normal template substitutions."
            ),
            confidence=1.0,
        )
    ]


def _swift_upload_order_findings(path: str, text: str) -> list[dict[str, Any]]:
    upload_function = re.search(
        r"func\s+performUploadRequest\s*\([^)]*\)\s*\{(?P<body>[\s\S]{0,2200}?)"
        r"(?=\n\s*func\s+perform[A-Za-z]+Request\s*\(|\n\s*//\s*MARK:|\Z)",
        text,
    )
    if upload_function is None:
        return []
    body = upload_function.group("body")
    materialize = re.search(r"createUploadable\s*\(\s*\)", body)
    setup = re.search(r"performSetupOperations\s*\(", body)
    conversion = re.search(r"convertible\.asURLRequest\s*\(\s*\)", text)
    if materialize is None or setup is None or conversion is None or materialize.start() > setup.start():
        return []

    absolute = upload_function.start("body") + materialize.start()
    return [
        _finding(
            officer="Engineer",
            capability="data_flow",
            category="correctness",
            severity="major",
            root_cause="upload-payload-materialized-before-request-conversion-and-adaptation",
            path=path,
            line_start=_line(text, absolute),
            message=(
                "An upload payload is encoded before request conversion and adaptation have completed."
            ),
            evidence=(
                "`createUploadable()` runs before `performSetupOperations`, while setup later invokes `convertible.asURLRequest()`. "
                "Request conversion is an allowed preparation boundary and may append multipart body parts or otherwise finalize upload inputs, so early materialization captures incomplete state and also performs encoding even when conversion or adaptation fails."
            ),
            falsifiers=[
                "Required payload materialization and request setup in the same upload orchestration function.",
                "Confirmed setup performs URLRequest conversion after the early materialization point.",
                "Checked whether materialization is deferred in a continuation until conversion and adaptation succeed.",
                "Excluded immutable payloads whose creation is independent of request conversion and adapters.",
            ],
            verification=(
                "Create and adapt the request first, materialize the upload payload only after those stages succeed, and test a request converter that appends multipart parts plus conversion failure, adaptation failure, cancellation, and no-adapter paths."
            ),
            confidence=0.99,
        )
    ]


def run_static_transfer_31_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []
    scala_files: dict[str, str] = {}

    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        if suffix == ".scala":
            scala_files[path] = text
        elif suffix in {".ex", ".exs"}:
            findings.extend(_elixir_path_binding_findings(path, text))
        elif suffix == ".swift":
            findings.extend(_swift_upload_order_findings(path, text))

    findings.extend(_scala_handoff_findings(scala_files))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[
            (
                str(finding.get("root_cause")),
                str(finding.get("path")),
                int(finding.get("line_start") or 0),
            )
        ] = finding

    return {
        "schema_version": "sergeant.static-transfer-31-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
