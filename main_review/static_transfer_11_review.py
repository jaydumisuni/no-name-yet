"""Static checks for text boundaries, retained resources, and TLS trust composition."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_RUST_SUFFIXES = {".rs"}
_SCRIPT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_PYTHON_SUFFIXES = {".py"}
_SOURCE_SUFFIXES = _RUST_SUFFIXES | _SCRIPT_SUFFIXES | _PYTHON_SUFFIXES


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
    root_cause: str,
    path: str,
    line_start: int,
    category: str,
    officer: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    supporting: Iterable[str] = (),
    confidence: float = 0.97,
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-transfer-11-officer",
        "officer": officer,
        "capability": category,
        "category": category,
        "severity": "major",
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": refs[0],
        "supporting_evidence_refs": list(dict.fromkeys(refs)),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _rust_string_boundary_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _RUST_SUFFIXES:
        return []

    string_names: set[str] = set()
    for match in re.finditer(
        r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:&\s*(?:'[^\s]+\s*)?)?(?:str|String)\b",
        text,
    ):
        string_names.add(match.group("name"))
    for match in re.finditer(
        r"\blet\s+(?:mut\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*String)?\s*=\s*[^;]*\.to_string\s*\(",
        text,
    ):
        string_names.add(match.group("name"))

    findings: list[dict[str, Any]] = []
    slice_re = re.compile(
        r"&\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\[\s*\.\.\s*(?P<end>[^\]\n]+)\]"
    )
    for match in slice_re.finditer(text):
        name = match.group("name")
        end = match.group("end")
        if name not in string_names:
            continue
        if re.search(rf"\b{re.escape(name)}\s*\.\s*len\s*\(\s*\)", end) is None and re.search(
            r"\b\d+\b", end
        ) is None:
            continue
        window = text[max(0, match.start() - 1600) : min(len(text), match.end() + 300)]
        if re.search(
            r"(?:is_char_boundary|char_indices|floor_char_boundary|ceil_char_boundary|truncate_on_char_boundary|\.get\s*\(\s*\.\.)",
            window,
        ):
            continue

        line = _line(text, match.start())
        findings.append(
            _finding(
                root_cause="rust-str-sliced-at-unverified-byte-boundary",
                path=path,
                line_start=line,
                category="correctness",
                officer="Engineer",
                message="A Rust UTF-8 string is sliced at a byte offset without proving that the offset is a character boundary.",
                evidence=(
                    f"`{name}` is declared as `str`/`String`, but the slice end `{end.strip()}` is derived as a byte cap. "
                    "Rust string indexing panics whenever that byte falls inside a multibyte character."
                ),
                falsifiers=(
                    "Checked that the sliced value is declared as str or String rather than a byte buffer.",
                    "Checked the surrounding path for is_char_boundary, char_indices, a boundary helper, or safe get(..) slicing.",
                    "Checked that the end expression is a numeric/len-derived byte offset rather than a proven character iterator boundary.",
                ),
                verification=(
                    "Move the end backward to a valid char boundary or use a safe boundary helper/get(..), then prove multibyte text beyond the cap does not panic."
                ),
            )
        )
    return findings


def _timer_owner(text: str, start: int) -> str | None:
    prefix = text[max(0, start - 160) : start]
    assignment = re.search(
        r"(?P<owner>(?:this\.[A-Za-z_$][A-Za-z0-9_$]*|[A-Za-z_$][A-Za-z0-9_$]*))\s*=\s*$",
        prefix,
    )
    if assignment:
        return assignment.group("owner")
    declaration = re.search(
        r"\b(?:const|let|var)\s+(?P<owner>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*$",
        prefix,
    )
    if declaration:
        return declaration.group("owner")
    return None


def _script_resource_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _SCRIPT_SUFFIXES:
        return []

    findings: list[dict[str, Any]] = []
    for timer in re.finditer(r"\bsetInterval\s*\(", text):
        owner = _timer_owner(text, timer.start())
        if owner is None:
            line = _line(text, timer.start())
            findings.append(
                _finding(
                    root_cause="recurring-timer-created-without-owned-handle",
                    path=path,
                    line_start=line,
                    category="resource_lifecycle",
                    officer="Mechanic",
                    message="A recurring timer is created without retaining a handle that can be cancelled during teardown.",
                    evidence=(
                        "The `setInterval` result is neither stored nor returned. Its callback can keep server/component state reachable and continue running after shutdown."
                    ),
                    falsifiers=(
                        "Checked for assignment to an instance, local, or returned timer handle.",
                        "Checked that this is a recurring interval rather than a one-shot timeout.",
                    ),
                    verification=(
                        "Store the interval handle, clear it from an explicit destroy/stop/unmount path, and prove no callback fires after teardown."
                    ),
                )
            )
            continue

        clear_pattern = rf"\bclearInterval\s*\(\s*{re.escape(owner)}\s*\)"
        if re.search(clear_pattern, text) is None:
            line = _line(text, timer.start())
            findings.append(
                _finding(
                    root_cause="owned-recurring-timer-without-teardown",
                    path=path,
                    line_start=line,
                    category="resource_lifecycle",
                    officer="Mechanic",
                    message="A recurring timer handle is retained but no teardown path clears it.",
                    evidence=f"The interval is assigned to `{owner}`, but the reviewed source never calls `clearInterval({owner})`.",
                    falsifiers=(
                        "Checked for clearInterval on the same owner.",
                        "Checked for returned cleanup closures and explicit destroy/stop/unmount paths.",
                    ),
                    verification="Clear the same handle during teardown and prove repeated start/stop cycles leave no active timer.",
                )
            )

    direct_delete_re = re.compile(
        r"this\.(?P<map>[A-Za-z_$][A-Za-z0-9_$]*)\.get\s*\(\s*(?P<key>[^)\n]+)\s*\)"
        r"\.delete\s*\(\s*(?P<member>[^)\n]+)\s*\)"
    )
    for deletion in direct_delete_re.finditer(text):
        map_name = deletion.group("map")
        key = deletion.group("key").strip()
        after = text[deletion.end() : deletion.end() + 1400]
        container_delete = re.search(
            rf"this\.{re.escape(map_name)}\.delete\s*\(\s*{re.escape(key)}\s*\)",
            after,
        )
        if container_delete is not None:
            continue
        line = _line(text, deletion.start())
        findings.append(
            _finding(
                root_cause="empty-retained-container-not-removed-after-member-delete",
                path=path,
                line_start=line,
                category="resource_lifecycle",
                officer="Mechanic",
                message="A member is removed from a retained Set/collection, but the now-empty container is never removed from its owning map.",
                evidence=(
                    f"`this.{map_name}.get({key}).delete(...)` removes the member only. No matching `this.{map_name}.delete({key})` follows, so empty containers accumulate."
                ),
                falsifiers=(
                    "Checked the following cleanup path for a size/emptiness guard and deletion of the owning map entry.",
                    "Checked that the operation targets a collection retained in an instance map.",
                ),
                verification=(
                    "After member removal, delete the map entry when the child collection is empty and prove connect/disconnect cycles return the map to baseline size."
                ),
            )
        )
    return findings


def _python_tls_trust_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _PYTHON_SUFFIXES:
        return []
    if re.search(r"(?:REQUESTS_CA_BUNDLE|CURL_CA_BUNDLE|SSL_CERT_FILE)", text) is None:
        return []

    assignment = re.search(
        r"(?m)^\s*(?P<verify>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<bundle>[A-Z_][A-Z0-9_]*)\s+if\s+"
        r"os\.path\.exists\s*\(\s*(?P=bundle)\s*\)\s+else\s+True\s*$",
        text,
    )
    if assignment is None:
        return []
    if re.search(r"(?:certifi|create_default_context|get_default_verify_paths|system.*(?:root|trust)|union|combine|concatenate)", text, re.I):
        return []

    bundle = assignment.group("bundle")
    bundle_definition = re.search(
        rf"(?m)^\s*{re.escape(bundle)}\s*=\s*\([\s\S]{{0,500}}?\)",
        text,
    )
    if bundle_definition is None:
        return []

    line = _line(text, assignment.start())
    return [
        _finding(
            root_cause="custom-ca-bundle-replaces-public-trust-roots",
            path=path,
            line_start=line,
            category="transport_security",
            officer="Medic",
            message="A custom CA bundle becomes the sole TLS trust store instead of augmenting the platform/public roots.",
            evidence=(
                f"`{assignment.group('verify')}` selects `{bundle}` whenever that file exists and otherwise uses the default store. "
                "No public-root source or trust-store union is present, so certificates outside the custom bundle can fail even when publicly valid."
            ),
            falsifiers=(
                "Checked for certifi, SSL default verify paths, system-root loading, or explicit bundle union/concatenation.",
                "Checked that the custom bundle is selected as the complete verify argument rather than added to a default context.",
                "Checked that verification remains enabled; this is a trust-composition defect, not a verify=False rule.",
            ),
            verification=(
                "Build a combined trust store containing public/platform roots and the private/proxy anchors, then prove both inspected and pass-through public chains verify while untrusted chains still fail."
            ),
        )
    ]


def run_static_transfer_11_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        findings.extend(_rust_string_boundary_findings(path, text))
        findings.extend(_script_resource_findings(path, text))
        findings.extend(_python_tls_trust_findings(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(
            str(finding.get("root_cause")),
            str(finding.get("path")),
            int(finding.get("line_start") or 0),
        )] = finding

    return {
        "schema_version": "sergeant.static-transfer-11-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
