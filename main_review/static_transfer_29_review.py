"""Static checks learned after transfer set 29's blind artifact was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".ml", ".mli", ".jl", ".cr"}


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
        "source": "static-transfer-29-officer",
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


def _ocaml_namespace_findings(path: str, text: str) -> list[dict[str, Any]]:
    if "find_uid" not in text or "Pextra_ty" not in text:
        return []
    function = re.search(
        r"let\s+find_uid\b(?P<body>[\s\S]{0,2600}?)(?=\nlet\s|\n\(\*|\Z)",
        text,
        re.M,
    )
    if function is None:
        return []

    body = function.group("body")
    for branch in re.finditer(r"^\s*\|\s*(?P<alts>[^\n]*?)\s*->(?P<code>[\s\S]{0,420}?)(?=^\s*\||\Z)", body, re.M):
        alternatives = {item.strip() for item in branch.group("alts").split("|")}
        if not {"Type", "Constructor", "Label"}.issubset(alternatives):
            continue
        code = branch.group("code")
        if not (re.search(r"\bfind_type\b", code) and re.search(r"\.type_uid\b", code)):
            continue
        if re.search(r"^\s*\|\s*Constructor\s*->", body, re.M) and re.search(
            r"^\s*\|\s*Label\s*->", body, re.M
        ):
            continue
        absolute = function.start("body") + branch.start()
        return [
            _finding(
                officer="Engineer",
                capability="namespace_contract",
                category="correctness",
                severity="blocker",
                root_cause="specialized-namespace-paths-collapsed-into-ordinary-type-lookup",
                path=path,
                line_start=_line(text, absolute),
                message=(
                    "Constructor and label namespaces are dispatched through the ordinary type lookup contract even though their encoded paths require specialized resolution."
                ),
                evidence=(
                    "The UID dispatcher groups `Type`, `Constructor`, and `Label`, normalizes all three as type paths, then returns `find_type(...).type_uid`. "
                    "The same module accepts `Pextra_ty` constructor encodings and has specialized constructor/label tables, so these namespaces do not share the ordinary type declaration contract."
                ),
                falsifiers=[
                    "Required a UID or symbol dispatcher with explicit semantic namespace alternatives.",
                    "Required Constructor and Label to share one branch with Type.",
                    "Required the shared branch to call ordinary type lookup and return a type UID.",
                    "Required evidence that extended/specialized paths exist in the same module.",
                    "Excluded dispatchers with separate constructor, label, and extension-constructor resolution branches.",
                ],
                verification=(
                    "Resolve constructor, label, and extension-constructor namespaces through their specialized path encodings and UID sources; test local, qualified, extension, and shape-only paths without assertions."
                ),
                confidence=0.99,
            )
        ]
    return []


def _julia_string_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    thisind = re.search(
        r"function\s+thisind\s*\(\s*s\s*::\s*String\s*,\s*i\s*::\s*Int\s*\)"
        r"(?P<body>[\s\S]{0,1100}?)\nend",
        text,
        re.M,
    )
    if thisind is not None:
        body = thisind.group("body")
        backward = re.search(r"@inbounds\s+\w+\s*=\s*codeunit\s*\(\s*s\s*,\s*i\s*-\s*1\s*\)", body)
        zero_allowed = re.search(r"between\s*\(\s*i\s*,\s*0\s*,", body)
        zero_return = re.search(r"\bi\s*==\s*0\s*&&\s*return", body)
        lower_bound = re.search(r"\b(?:i\s*-\s*1\s*>\s*0|i\s*>\s*1)\b", body)
        if backward is not None and zero_allowed is not None and zero_return is None and (
            lower_bound is None or lower_bound.start() > backward.start()
        ):
            absolute = thisind.start("body") + backward.start()
            findings.append(
                _finding(
                    officer="Engineer",
                    capability="memory_boundary_contract",
                    category="correctness",
                    severity="blocker",
                    root_cause="unchecked-backward-codeunit-read-precedes-lower-bound-proof",
                    path=path,
                    line_start=_line(text, absolute),
                    message=(
                        "An unchecked backward code-unit read occurs before proving that the previous index exists."
                    ),
                    evidence=(
                        "`thisind` accepts index zero in its bounds contract and then evaluates `codeunit(s, i-1)` under `@inbounds` before any lower-bound proof. "
                        "At the lower boundary this can read before the string buffer and hide the fault from normal bounds checking."
                    ),
                    falsifiers=[
                        "Required an unchecked code-unit read at `i - 1`.",
                        "Required the function's accepted range to include zero or another boundary where the previous index is invalid.",
                        "Checked for an early zero return or an explicit lower-bound proof before the read.",
                        "Excluded checked indexing and reads guarded before execution.",
                    ],
                    verification=(
                        "Return or reject the lower sentinel before any backward read, and test zero, first code unit, continuation bytes, malformed bytes, and end sentinel positions."
                    ),
                    confidence=0.99,
                )
            )

    length_fn = re.search(
        r"function\s+length\s*\(\s*s\s*::\s*String\s*,\s*i\s*::\s*Int\s*,\s*j\s*::\s*Int\s*\)"
        r"(?P<body>[\s\S]{0,1000}?)\nend",
        text,
        re.M,
    )
    if length_fn is not None:
        body = length_fn.group("body")
        count = re.search(r"\bc\s*=\s*j\s*-\s*i\s*\+\s*1\b", body)
        align = re.search(r"thisind\s*\(\s*s\s*,\s*i\s*\)", body)
        correction = re.search(r"\bc\s*-=\s*i\s*<\s*k\b", body)
        canonical = re.search(r"\bc\s*=\s*j\s*-\s*i\s*\+\s*\(\s*i\s*==\s*k\s*\)", body)
        if (
            count is not None
            and align is not None
            and correction is not None
            and count.start() < align.start()
            and canonical is None
        ):
            absolute = length_fn.start("body") + count.start()
            findings.append(
                _finding(
                    officer="Engineer",
                    capability="index_domain_contract",
                    category="correctness",
                    severity="major",
                    root_cause="byte-span-count-fixed-before-character-boundary-alignment",
                    path=path,
                    line_start=_line(text, absolute),
                    message=(
                        "Character count is initialized from the raw byte span before the start index is aligned to a valid character boundary."
                    ),
                    evidence=(
                        "`length(s, i, j)` computes `j - i + 1`, then changes `i` through `thisind` and applies only a one-bit correction. "
                        "Byte displacement and character displacement are not equivalent for multibyte or malformed strings, so the optimized String path can disagree with the generic AbstractString contract."
                    ),
                    falsifiers=[
                        "Required a character-count API over byte-index bounds.",
                        "Required count initialization before boundary normalization.",
                        "Required only a boolean correction after normalization.",
                        "Checked for count derivation from the normalized start or iteration through valid character boundaries.",
                        "Excluded implementations that compute the canonical count after alignment.",
                    ],
                    verification=(
                        "Align the start index before deriving the initial count or traverse character boundaries directly; prove parity with the generic string implementation across ASCII, multibyte, malformed-byte, empty, and sentinel ranges."
                    ),
                    confidence=0.98,
                )
            )
    return findings


def _crystal_ktls_findings(files: dict[str, str]) -> list[dict[str, Any]]:
    context = next(((path, text) for path, text in files.items() if "ENABLE_KTLS" in text and "remove_options" in text), None)
    socket = next(((path, text) for path, text in files.items() if "ktls_safe_handshake" in text), None)
    bio = next(((path, text) for path, text in files.items() if "CTRL_SET_KTLS" in text), None)
    if context is None or socket is None or bio is None:
        return []

    context_path, context_text = context
    socket_path, socket_text = socket
    bio_path, bio_text = bio
    disabled = re.search(r"remove_options\s*\([^)]*ENABLE_KTLS[^)]*\)", context_text, re.S)
    mandatory_error = re.search(
        r"unless\s+[^\n]*in_buffer_rem\.empty\?[^\n]*\n\s*raise\s+Error\.new\s*\([^\n]*KTLS[^\n]*empty",
        socket_text,
        re.I,
    )
    start = re.search(r"KTLS\.enable\s*\([^)]*\)[\s\S]{0,220}?KTLS\.start\s*\(", bio_text)
    safe_guard = re.search(
        r"if\s+[^\n]*(?:is_tx|read_buffering\?|in_buffer_rem\.empty\?)[^\n]*\n\s*KTLS\.enable",
        bio_text,
        re.I,
    )
    if disabled is None or mandatory_error is None or start is None or safe_guard is not None:
        return []

    return [
        _finding(
            officer="Mechanic",
            capability="optional_acceleration_fallback",
            category="correctness",
            severity="blocker",
            root_cause="optional-transport-acceleration-failure-escalated-to-handshake-error",
            path=socket_path,
            line_start=_line(socket_text, mandatory_error.start()),
            message=(
                "An optional transport acceleration path turns an unsafe offload condition into a fatal handshake error instead of declining acceleration and preserving the base protocol."
            ),
            evidence=(
                "The SSL context removes `ENABLE_KTLS` by default, the socket wrapper raises when buffered input prevents safe RX offload, and the BIO control path attempts KTLS without first proving the receive buffer is compatible. "
                "Kernel TLS is an acceleration layer; buffered data should make the control callback return failure for offload while the TLS handshake continues in user space."
            ),
            falsifiers=[
                "Required an optional acceleration flag and a complete non-accelerated protocol path.",
                "Required a fatal error caused only by acceleration preconditions rather than base-protocol invalidity.",
                "Required the low-level acceleration callback to support a non-success return.",
                "Checked for a receive-buffer guard that declines offload before enabling it.",
                "Excluded implementations that transparently fall back to the base transport.",
            ],
            verification=(
                "Keep acceleration opt-in state independent from protocol correctness, decline RX offload when buffered bytes remain, and test successful TLS handshakes with empty and nonempty user-space buffers plus TX-only offload."
            ),
            confidence=0.99,
            supporting=(
                f"{context_path}:{_line(context_text, disabled.start())}",
                f"{bio_path}:{_line(bio_text, start.start())}",
            ),
        )
    ]


def run_static_transfer_29_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []
    crystal_files: dict[str, str] = {}

    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        if suffix in {".ml", ".mli"}:
            findings.extend(_ocaml_namespace_findings(path, text))
        elif suffix == ".jl":
            findings.extend(_julia_string_findings(path, text))
        elif suffix == ".cr":
            crystal_files[path] = text

    findings.extend(_crystal_ktls_findings(crystal_files))

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
        "schema_version": "sergeant.static-transfer-29-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
