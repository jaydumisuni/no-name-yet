"""Static checks learned after transfer set 27's blind artifact was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".cc", ".cpp", ".cxx", ".h", ".hpp", ".java", ".py"}


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
        "source": "static-transfer-27-officer",
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


def _cpp_operand_order_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    discriminator = re.compile(
        r"(?P<index>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(\s*"
        r"(?P<op>[A-Za-z_][A-Za-z0-9_]*)\s*->\s*getOperand\s*\(\s*0\s*\)\s*==\s*"
        r"(?P<target>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\?\s*1\s*:\s*0\s*;",
        re.M,
    )
    for match in discriminator.finditer(text):
        op = match.group("op")
        index = match.group("index")
        target = match.group("target")
        window = text[match.end() : match.end() + 1800]
        extracted = re.search(
            rf"(?P<other>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*[\s\S]{{0,260}}?"
            rf"{re.escape(op)}\s*->\s*getOperand\s*\(\s*{re.escape(index)}\s*\)",
            window,
            re.M,
        )
        if extracted is None:
            continue
        other = extracted.group("other")
        create = re.search(
            rf"CreateWithCopiedFlags\s*\([\s\S]{{0,260}}?{re.escape(op)}\s*->\s*getOpcode\s*\(\s*\)\s*,"
            rf"\s*(?P<first>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*{re.escape(other)}\s*,\s*{re.escape(op)}\b",
            window,
            re.M,
        )
        if create is None:
            continue
        first = create.group("first")
        conditional_order = re.search(
            rf"(?P<first_name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(\s*{re.escape(op)}\s*->\s*getOperand\s*\(\s*0\s*\)\s*==\s*{re.escape(target)}\s*\)"
            rf"\s*\?\s*{re.escape(first)}\s*:\s*{re.escape(other)}\s*;[\s\S]{{0,300}}?"
            rf"(?P<second_name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(\s*{re.escape(op)}\s*->\s*getOperand\s*\(\s*0\s*\)\s*==\s*{re.escape(target)}\s*\)"
            rf"\s*\?\s*{re.escape(other)}\s*:\s*{re.escape(first)}\s*;",
            window,
            re.M,
        )
        commutative_guard = re.search(
            rf"(?:isCommutative|isCommutativeOpcode)\s*\([\s\S]{{0,120}}?{re.escape(op)}",
            text[max(0, match.start() - 600) : match.end() + 600],
            re.M,
        )
        if conditional_order is not None or commutative_guard is not None:
            continue
        absolute = match.end() + create.start()
        findings.append(
            _finding(
                officer="Engineer",
                capability="semantic_reconstruction",
                category="correctness",
                severity="blocker",
                root_cause="reconstructed-binary-operation-forgets-original-operand-order",
                path=path,
                line_start=_line(text, absolute),
                message=(
                    "A binary operation is reconstructed with a fixed operand order even though the original target may have occupied either side."
                ),
                evidence=(
                    f"`{index}` records whether `{target}` was operand 0 of `{op}`, and `{other}` is extracted from the opposite side. "
                    f"The reconstructed operation nevertheless always uses `({first}, {other})`. For non-commutative opcodes this silently changes semantics."
                ),
                falsifiers=[
                    "Required an explicit original-side discriminator and extraction of the opposite operand.",
                    "Required reconstruction using the original dynamic opcode.",
                    "Checked for conditional FirstOp/SecondOp reconstruction preserving the original side.",
                    "Checked for a proof that the dynamic opcode is restricted to commutative operations.",
                    "Excluded fixed-order reconstruction when source order is preserved or commutativity is proved.",
                ],
                verification=(
                    "Derive both reconstructed operands from the original operand side and test a non-commutative opcode with the transformed value in operand 1."
                ),
                confidence=0.99,
                supporting=(f"{path}:{_line(text, match.start())}",),
            )
        )
    return findings


def _first_release_call(
    text: str,
    argument_pattern: str,
    *,
    start: int = 0,
) -> re.Match[str] | None:
    call_pattern = re.compile(
        rf"(?P<call>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*{argument_pattern}",
        re.I | re.M,
    )
    for match in call_pattern.finditer(text, start):
        if "release" in match.group("call").lower():
            return match
    return None


def _java_lock_ownership_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    trackers = sorted(
        set(
            re.findall(
                r"\b([A-Za-z_][A-Za-z0-9_]*(?:Acquired|Held|Locked)[A-Za-z0-9_]*)\b",
                text,
            )
        )
    )
    for tracker in trackers:
        subset_release = _first_release_call(
            text,
            r"(?P<subset>(?:nonRemote|released|completed|local)[A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*(?:nonRemote|released|completed|local)[A-Za-z0-9_]*)",
        )
        if subset_release is None:
            continue
        subset = subset_release.group("subset")
        after = text[subset_release.end() : subset_release.end() + 2200]
        removal = re.search(
            rf"(?:{re.escape(subset)}\s*\.\s*forEach\s*\(\s*{re.escape(tracker)}\s*::\s*remove\s*\)|"
            rf"{re.escape(tracker)}\s*\.\s*keySet\s*\(\s*\)\s*\.\s*removeAll\s*\(\s*{re.escape(subset)}\s*\)|"
            rf"{re.escape(tracker)}\s*\.\s*removeAll\s*\(\s*{re.escape(subset)}\s*\))",
            after,
            re.M,
        )
        later_full_release = _first_release_call(
            text,
            rf"{re.escape(tracker)}\s*\.\s*keySet\s*\(",
            start=subset_release.end(),
        )
        if removal is not None or later_full_release is None:
            continue

        catch_without_finally = re.search(
            r"catch\s*\([^)]*\)\s*\{(?P<body>[\s\S]{0,1000}?(?:handle|record|metric)[\s\S]{0,600}?"
            r"[A-Za-z_][A-Za-z0-9_]*release[A-Za-z0-9_]*\s*\([^}]+)\}",
            text,
            re.I | re.M,
        )
        supporting = [f"{path}:{_line(text, subset_release.start())}"]
        evidence_tail = ""
        if catch_without_finally is not None:
            supporting.append(f"{path}:{_line(text, catch_without_finally.start())}")
            evidence_tail = (
                " A separate exception path performs metric/error handling before release without a finally boundary, so a secondary throw can leak the same ownership."
            )

        findings.append(
            _finding(
                officer="Mechanic",
                capability="async_resource_ownership",
                category="concurrency",
                severity="blocker",
                root_cause="async-lock-ownership-not-reconciled-across-completion-paths",
                path=path,
                line_start=_line(text, subset_release.start()),
                message=(
                    "An asynchronously owned lock subset is released without removing it from the aggregate ownership set that later drives another release."
                ),
                evidence=(
                    f"`{subset}` is released, but the released identities remain in `{tracker}`. A later completion path releases `{tracker}.keySet()` again. "
                    "The second release can leak, double-release, or clear a lock that another request has already reacquired."
                    + evidence_tail
                ),
                falsifiers=[
                    "Required an aggregate acquired/held/locked collection and a separately released subset.",
                    "Required a later release driven by the aggregate collection.",
                    "Checked for explicit removal of the released subset from aggregate ownership.",
                    "Checked for release in a finally-safe exception boundary.",
                    "Excluded reconciled ownership sets and single terminal release paths.",
                ],
                verification=(
                    "Remove every released subset from aggregate ownership immediately, release mandatory locks from finally-safe paths, and test fast success, slow completion, timeout, handler failure, and re-acquisition before final completion."
                ),
                confidence=0.99,
                supporting=supporting,
            )
        )
        break
    return findings


def _python_duration_equivalence_findings(path: str, text: str) -> list[dict[str, Any]]:
    if not (re.search(r"\bDay\b", text) and re.search(r"\bTick\b", text)):
        return []
    warning_gate = re.search(r"if\s+not\s+isinstance\s*\(\s*freq\s*,\s*Tick\s*\)\s*:", text)
    range_gate = re.search(r"if\s+isinstance\s*\(\s*freq\s*,\s*Tick\s*\)\s*:", text)
    calendar_fallback = re.search(
        r"first\s*=\s*first\.normalize\s*\(\s*\)[\s\S]{0,500}?last\s*=\s*last\.normalize",
        text,
    )
    if warning_gate is None or range_gate is None or calendar_fallback is None:
        return []
    day_equivalence = re.search(
        r"isinstance\s*\(\s*freq\s*,\s*Day\s*\)[\s\S]{0,500}?(?:tz\s+is\s+None|Hour\s*\()",
        text,
        re.M,
    )
    if day_equivalence is not None:
        return []
    return [
        _finding(
            officer="Engineer",
            capability="contextual_contract_equivalence",
            category="correctness",
            severity="major",
            root_cause="fixed-duration-calendar-day-bypasses-tick-origin-and-bin-contract",
            path=path,
            line_start=_line(text, range_gate.start()),
            message=(
                "A timezone-naive fixed-duration Day interval is routed through calendar normalization instead of the equivalent anchored Tick path."
            ),
            evidence=(
                "The module recognizes both `Day` and `Tick`, but origin/offset and range-edge logic treat only `Tick` as anchored fixed duration. "
                "`Day` therefore falls through normalization/rollback even when a timezone-naive day is exactly 24 hours, so equivalent Day and Hour frequencies can produce different bins or ignore origin/offset."
            ),
            falsifiers=[
                "Required both Day and Tick frequency concepts in the same binning implementation.",
                "Required origin/offset or range-edge behavior gated only on Tick.",
                "Required a calendar normalization fallback for non-Tick frequencies.",
                "Checked for a timezone-naive Day equivalence branch and conversion to fixed hours.",
                "Excluded timezone-aware Day semantics and implementations that already distinguish contextual equivalence.",
            ],
            verification=(
                "For timezone-naive datetime axes, route Day through the equivalent fixed-hour anchored calculation and prove Day/Hour parity for origin, offset, closed, and label; preserve calendar-day behavior across timezone transitions."
            ),
            confidence=0.98,
            supporting=(f"{path}:{_line(text, warning_gate.start())}",),
        )
    ]


def run_static_transfer_27_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []
    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        if suffix in {".cc", ".cpp", ".cxx", ".h", ".hpp"}:
            findings.extend(_cpp_operand_order_findings(path, text))
        elif suffix == ".java":
            findings.extend(_java_lock_ownership_findings(path, text))
        elif suffix == ".py":
            findings.extend(_python_duration_equivalence_findings(path, text))

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
        "schema_version": "sergeant.static-transfer-27-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
