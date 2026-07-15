from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]
cli_path = root / "main_review" / "cloudflare_cli.py"
test_path = root / "tests" / "test_cloudflare_mission_qualification.py"

cli = cli_path.read_text(encoding="utf-8")
old = '''            verdict_matches = not expected_verdict or report.get("verdict") == expected_verdict
            passed = verdict_matches and bool(matching)
            results.append({
'''
new = '''            verdict_matches = not expected_verdict or report.get("verdict") == expected_verdict
            coverage = report.get("coverage", {}) if isinstance(report.get("coverage"), dict) else {}
            reviewed_files = {
                str(path) for path in coverage.get("files_reviewed", []) if str(path).strip()
            } if isinstance(coverage.get("files_reviewed", []), list) else set()
            reviewed_areas = {
                str(area).strip().lower()
                for area in coverage.get("areas", [])
                if str(area).strip()
            } if isinstance(coverage.get("areas", []), list) else set()
            coverage_matches = (
                (not expected_path or expected_path in reviewed_files)
                and (not expected_category or expected_category in reviewed_areas)
            )
            passed = verdict_matches and bool(matching) and coverage_matches
            results.append({
'''
if cli.count(old) != 1:
    raise RuntimeError(f"coverage qualification: expected one match, found {cli.count(old)}")
cli = cli.replace(old, new, 1)
old_response = '''                    "matching_findings": matching,
                    "coverage": report.get("coverage", {}),
'''
new_response = '''                    "matching_findings": matching,
                    "coverage": coverage,
                    "coverage_matches": coverage_matches,
'''
if cli.count(old_response) != 1:
    raise RuntimeError(f"coverage diagnostics: expected one match, found {cli.count(old_response)}")
cli = cli.replace(old_response, new_response, 1)
cli_path.write_text(cli, encoding="utf-8")

tests = test_path.read_text(encoding="utf-8")
addition = '''

@pytest.mark.parametrize(
    "coverage",
    [
        {"files_reviewed": [], "areas": []},
        {"files_reviewed": ["src/auth.py"], "areas": ["correctness"]},
        {"files_reviewed": ["src/other.py"], "areas": ["security"]},
    ],
)
def test_mission_qualification_rejects_missing_or_incorrect_coverage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    coverage: dict[str, list[str]],
) -> None:
    root = fixture(tmp_path)
    payload = valid_payload()
    payload["coverage"] = coverage
    monkeypatch.setattr(cloudflare_cli, "invoke_json", lambda *args, **kwargs: payload)

    result = cloudflare_cli.qualify_models(
        settings(),
        root=root,
        changed_files=["src/auth.py"],
        expected_verdict="BLOCK",
        expected_path="src/auth.py",
        expected_category="security",
        expected_severity="blocker",
        expected_evidence="shell=True",
    )

    assert result["passed_count"] == 0
    assert all(item["passed"] is False for item in result["models"])
    assert all(item["response"]["coverage_matches"] is False for item in result["models"])
'''
if "test_mission_qualification_rejects_missing_or_incorrect_coverage" in tests:
    raise RuntimeError("coverage regression test already exists")
marker = "\n\ndef test_live_workflow_uses_mission_qualified_two_member_roster() -> None:\n"
if tests.count(marker) != 1:
    raise RuntimeError(f"test insertion marker: expected one match, found {tests.count(marker)}")
tests = tests.replace(marker, addition + marker, 1)
test_path.write_text(tests, encoding="utf-8")

assert cli_path.read_text(encoding="utf-8").count("coverage_matches = (") == 1
print("Mission qualification coverage correction applied.")
