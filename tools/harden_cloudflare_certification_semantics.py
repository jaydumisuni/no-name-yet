from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} anchor, found {count}.")
    return text.replace(old, new, 1)


council = Path("main_review/cpl_council.py")
text = council.read_text(encoding="utf-8")
text = replace_once(
    text,
    'r"(?:shell\\s*=\\s*true|subprocess\\.(?:run|popen)|command\\s+injection|"\n',
    'r"(?:shell\\s*=\\s*true|command\\s+injection|"\n',
    "unsafe-shell root-cause regex",
)
old = '''def finding_key(finding: dict[str, Any]) -> tuple[object, ...]:
    """Identify one underlying defect across model wording and nearby line drift."""

    path = str(finding.get("path") or "").replace("\\\\", "/")
    category = str(finding.get("category") or "other").strip().lower()
    root_cause = finding_root_cause(finding)
    if root_cause:
        try:
            line_start = max(1, int(finding.get("line_start") or 1))
        except (TypeError, ValueError):
            line_start = 1
        line_window = (line_start - 1) // 10
        return path, category, root_cause, line_window

    message = re.sub(r"\\W+", " ", str(finding.get("message", "")).lower()).strip()
    return path, finding.get("line_start"), finding.get("line_end"), message
'''
new = '''def _finding_lines(finding: dict[str, Any]) -> tuple[int, int]:
    try:
        start = max(1, int(finding.get("line_start") or 1))
    except (TypeError, ValueError):
        start = 1
    try:
        end = max(start, int(finding.get("line_end") or start))
    except (TypeError, ValueError):
        end = start
    return start, end


def _line_distance(left: dict[str, Any], right: dict[str, Any]) -> int:
    left_start, left_end = _finding_lines(left)
    right_start, right_end = _finding_lines(right)
    if left_end >= right_start and right_end >= left_start:
        return 0
    return max(right_start - left_end, left_start - right_end)


def finding_key(finding: dict[str, Any]) -> tuple[object, ...]:
    """Return a stable exact identity; use ``findings_match`` for nearby variants."""

    path = str(finding.get("path") or "").replace("\\\\", "/")
    root_cause = finding_root_cause(finding)
    start, end = _finding_lines(finding)
    if root_cause:
        return path, root_cause, start, end

    category = str(finding.get("category") or "other").strip().lower()
    message = re.sub(r"\\W+", " ", str(finding.get("message", "")).lower()).strip()
    return path, category, start, end, message


def findings_match(left: dict[str, Any], right: dict[str, Any], *, max_line_distance: int = 10) -> bool:
    """Match one root cause across model wording and nearby line-range drift."""

    left_path = str(left.get("path") or "").replace("\\\\", "/")
    right_path = str(right.get("path") or "").replace("\\\\", "/")
    if not left_path or left_path != right_path:
        return False

    left_root = finding_root_cause(left)
    right_root = finding_root_cause(right)
    if left_root or right_root:
        return bool(left_root and left_root == right_root and _line_distance(left, right) <= max_line_distance)
    return finding_key(left) == finding_key(right)
'''
text = replace_once(text, old, new, "finding identity implementation")
old = '''    if model_count > 1:
        support: dict[tuple[object, ...], set[str]] = {}
        for report in passes:
            for finding in report.get("findings", []):
                support.setdefault(finding_key(finding), set()).add(str(report.get("model")))
        for report in passes:
            for finding in report.get("findings", []):
                if finding.get("severity") not in {"blocker", "major"} or len(support.get(finding_key(finding), set())) > 1:
                    continue
                specialist = CATEGORY_SPECIALIST.get(str(finding.get("category") or "other"), "correctness")
                gaps.append({
                    "type": "independent_confirmation",
                    "specialist": specialist,
                    "officer": SPECIALISTS[specialist].officer,
                    "reason": f"High-impact finding has one model source: {finding.get('message')}",
                    "target_finding": finding_reference(finding),
                })
'''
new = '''    if model_count > 1:
        confirmation_targets: list[dict[str, Any]] = []
        for report in passes:
            for finding in report.get("findings", []):
                if finding.get("severity") not in {"blocker", "major"}:
                    continue
                if any(findings_match(finding, existing) for existing in confirmation_targets):
                    continue
                confirmation_targets.append(finding)
                supporting_models = {
                    str(other.get("model"))
                    for other in passes
                    if other.get("model")
                    and any(findings_match(finding, candidate) for candidate in other.get("findings", []))
                }
                if len(supporting_models) > 1:
                    continue
                specialist = CATEGORY_SPECIALIST.get(str(finding.get("category") or "other"), "correctness")
                gaps.append({
                    "type": "independent_confirmation",
                    "specialist": specialist,
                    "officer": SPECIALISTS[specialist].officer,
                    "reason": f"High-impact finding has one model source: {finding.get('message')}",
                    "target_finding": finding_reference(finding),
                })
'''
text = replace_once(text, old, new, "independent support assessment")
council.write_text(text, encoding="utf-8")


runtime = Path("main_review/cpl_runtime.py")
text = runtime.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    finding_key,\n    finding_reference,\n",
    "    finding_key,\n    finding_reference,\n    findings_match,\n",
    "runtime findings_match import",
)
old = '''def _effective_passes(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rejected: set[tuple[object, ...]] = set()
    for report in passes:
        resolution = report.get("council_resolution")
        if not isinstance(resolution, dict) or resolution.get("status") != "answered":
            continue
        if resolution.get("disposition") not in {"rejected", "narrowed"}:
            continue
        target = resolution.get("target_finding")
        if isinstance(target, dict):
            rejected.add(finding_key(target))

    effective: list[dict[str, Any]] = []
    for report in passes:
        clone = dict(report)
        clone["findings"] = [finding for finding in report.get("findings", []) if finding_key(finding) not in rejected]
        effective.append(clone)
    return effective
'''
new = '''def _effective_passes(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for report in passes:
        resolution = report.get("council_resolution")
        if not isinstance(resolution, dict) or resolution.get("status") != "answered":
            continue
        if resolution.get("disposition") not in {"rejected", "narrowed"}:
            continue
        target = resolution.get("target_finding")
        if isinstance(target, dict):
            rejected.append(target)

    effective: list[dict[str, Any]] = []
    for report in passes:
        clone = dict(report)
        clone["findings"] = [
            finding
            for finding in report.get("findings", [])
            if not any(findings_match(finding, target) for target in rejected)
        ]
        effective.append(clone)
    return effective
'''
text = replace_once(text, old, new, "effective pass filtering")
old = '''def _annotate_confirmations(findings: list[dict[str, Any]], passes: list[dict[str, Any]]) -> None:
    by_key = {finding_key(finding): finding for finding in findings}
    for report in passes:
        resolution = report.get("council_resolution")
        if not isinstance(resolution, dict) or resolution.get("status") != "answered" or resolution.get("disposition") != "confirmed":
            continue
        target = resolution.get("target_finding")
        if not isinstance(target, dict):
            continue
        finding = by_key.get(finding_key(target))
        if finding is None:
            continue
        confirmations = finding.setdefault("council_confirmed_by", [])
        model = report.get("model")
        if model and model not in confirmations:
            confirmations.append(model)
'''
new = '''def _annotate_confirmations(findings: list[dict[str, Any]], passes: list[dict[str, Any]]) -> None:
    for report in passes:
        resolution = report.get("council_resolution")
        if not isinstance(resolution, dict) or resolution.get("status") != "answered" or resolution.get("disposition") != "confirmed":
            continue
        target = resolution.get("target_finding")
        if not isinstance(target, dict):
            continue
        finding = next((item for item in findings if findings_match(item, target)), None)
        if finding is None:
            continue
        confirmations = finding.setdefault("council_confirmed_by", [])
        model = report.get("model")
        if model and model not in confirmations:
            confirmations.append(model)
'''
text = replace_once(text, old, new, "confirmation annotation")
runtime.write_text(text, encoding="utf-8")


review = Path("main_review/llm_review.py")
text = review.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from .cpl_council import finding_key\n",
    "from .cpl_council import findings_match\n",
    "llm review finding matcher import",
)
old = '''def _merge_passes(passes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, float]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    for item in passes:
        for finding in item.get("findings", []):
            key = finding_key(finding)
            if key not in merged:
                merged[key] = {
                    **finding,
                    "supporting_models": [item.get("model")],
                    "supporting_specialists": [item.get("specialist")],
                }
            else:
                models = merged[key].setdefault("supporting_models", [])
                if item.get("model") not in models:
                    models.append(item.get("model"))
                specialists = merged[key].setdefault("supporting_specialists", [])
                if item.get("specialist") not in specialists:
                    specialists.append(item.get("specialist"))
    findings = list(merged.values())
'''
new = '''def _merge_passes(passes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, float]:
    findings: list[dict[str, Any]] = []
    for item in passes:
        for finding in item.get("findings", []):
            merged = next((existing for existing in findings if findings_match(existing, finding)), None)
            if merged is None:
                findings.append({
                    **finding,
                    "supporting_models": [item.get("model")],
                    "supporting_specialists": [item.get("specialist")],
                })
                continue
            models = merged.setdefault("supporting_models", [])
            if item.get("model") not in models:
                models.append(item.get("model"))
            specialists = merged.setdefault("supporting_specialists", [])
            if item.get("specialist") not in specialists:
                specialists.append(item.get("specialist"))
'''
text = replace_once(text, old, new, "pass finding merger")
review.write_text(text, encoding="utf-8")


cli = Path("main_review/cloudflare_cli.py")
text = cli.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from .cpl_runtime import run_cpl_review\n",
    "from .cpl_council import findings_match\nfrom .cpl_runtime import run_cpl_review\n",
    "Cloudflare CLI matcher import",
)
old = '''def _finding_supporting_models(finding: dict[str, Any]) -> list[str]:
    values = [
        *finding.get("supporting_models", []),
        *finding.get("council_confirmed_by", []),
    ]
    return sorted({str(value) for value in values if str(value).strip()})


'''
new = '''def _completed_matching_models(finding: dict[str, Any], passes: list[dict[str, Any]]) -> list[str]:
    return sorted({
        str(report.get("model"))
        for report in passes
        if report.get("model")
        and any(findings_match(finding, candidate) for candidate in report.get("findings", []))
    })


'''
text = replace_once(text, old, new, "Cloudflare support derivation")
text = replace_once(
    text,
    '''def _expected_finding_result(
    findings: list[dict[str, Any]],
    *,
''',
    '''def _expected_finding_result(
    findings: list[dict[str, Any]],
    passes: list[dict[str, Any]],
    *,
''',
    "expected finding signature",
)
old = '''        searchable = " ".join(
            str(finding.get(field, ""))
            for field in ("message", "evidence", "why_it_matters", "safer_alternative", "root_cause")
        ).lower()
        if expected_evidence and expected_evidence not in searchable:
            continue
        models = _finding_supporting_models(finding)
'''
new = '''        evidence = str(finding.get("evidence") or "").lower()
        if expected_evidence and (
            finding.get("evidence_verified") is not True
            or expected_evidence not in evidence
        ):
            continue
        models = _completed_matching_models(finding, passes)
'''
text = replace_once(text, old, new, "verified evidence and completed support")
text = replace_once(
    text,
    '''    expected_result = _expected_finding_result(
        effective_findings,
        expected_path=expected_path,
''',
    '''    expected_result = _expected_finding_result(
        effective_findings,
        passes,
        expected_path=expected_path,
''',
    "expected finding invocation",
)
cli.write_text(text, encoding="utf-8")


tests = Path("tests/test_cloudflare_certification_semantics.py")
text = tests.read_text(encoding="utf-8")
text = text.replace(
    "from main_review.cpl_council import finding_key, finding_root_cause\n",
    "from main_review.cpl_council import finding_key, finding_root_cause, findings_match\n",
)
text = text.replace(
    "    assert finding_key(first) == finding_key(second)\n",
    "    assert findings_match(first, second) is True\n",
)
text = text.replace(
    "    assert finding_key(first) != finding_key(second)\n",
    "    assert findings_match(first, second) is False\n",
)
append = '''

def test_subprocess_without_shell_is_not_classified_as_shell_injection() -> None:
    finding = _shell_finding(
        line=4,
        message="Subprocess environment inherits an unsafe PATH",
        evidence="subprocess.run([tool, '--version'], shell=False)",
    )
    finding["why_it_matters"] = "Executable resolution may select an unintended binary."

    assert finding_root_cause(finding) != "unsafe-shell-execution"


def test_adjacent_lines_match_across_fixed_bucket_boundaries() -> None:
    left = _shell_finding(line=10, message="Command injection", evidence="shell=True")
    right = _shell_finding(line=11, message="Shell command execution", evidence="shell=True")
    right["category"] = "correctness"

    assert findings_match(left, right) is True


def test_expected_contract_uses_verified_evidence_only() -> None:
    finding = _shell_finding(line=4, message="Unsafe command", evidence="subprocess.run(command)")
    finding["safer_alternative"] = "Avoid shell=True."
    finding["supporting_models"] = [MODEL_A, MODEL_B]
    result = cloudflare_cli._expected_finding_result(
        [finding],
        [
            {"model": MODEL_A, "findings": [finding]},
            {"model": MODEL_B, "findings": [finding]},
        ],
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=true",
        minimum_supporting_models=2,
    )

    assert result["passed"] is False


def test_expected_contract_ignores_claimed_models_without_matching_passes() -> None:
    finding = _shell_finding(line=4, message="Command injection", evidence="shell=True")
    finding["supporting_models"] = [MODEL_A, MODEL_B, "invented-model"]
    result = cloudflare_cli._expected_finding_result(
        [finding],
        [{"model": MODEL_A, "findings": [finding]}, {"model": MODEL_B, "findings": []}],
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=true",
        minimum_supporting_models=2,
    )

    assert result["passed"] is False
    assert result["matches"][0]["supporting_models"] == [MODEL_A]
'''
if "test_subprocess_without_shell_is_not_classified_as_shell_injection" not in text:
    text += append
tests.write_text(text, encoding="utf-8")
