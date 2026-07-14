from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from main_review.review_ingestion import ExternalReviewComment
from main_review.reviewer_comparison import (
    COMPARISON_SCHEMA,
    ReviewerComparisonError,
    _infer_category,
    _infer_severity,
    compare_reviewer_reports,
    extract_external_findings,
    extract_sergeant_findings,
    load_live_external_comments,
    main,
    match_findings,
    render_comparison_markdown,
)


def _sergeant_packet() -> dict:
    return {
        "verdict": {"verdict": "REQUEST_CHANGES"},
        "review_intelligence": {
            "ranked_findings": [
                {
                    "finding_id": "sgt-auth",
                    "capability": "security_taint",
                    "severity": "major",
                    "message": "Privileged route lacks a visible authorization guard.",
                    "evidence": "src/admin.py:12 defines POST /admin/reset without a role or permission guard.",
                    "path": "src/admin.py",
                    "line_start": 12,
                    "line_end": 12,
                    "root_cause": "authorization-gap",
                    "challenge_result": "survived: evidence is specific enough for review output",
                },
                {
                    "finding_id": "sgt-generic",
                    "capability": "data_flow",
                    "severity": "major",
                    "message": "Input may reach a sink.",
                    "evidence": "Patterns were both detected.",
                    "path": "src/api.py",
                    "challenge_result": "weakened: evidence is too generic",
                },
                {
                    "finding_id": "sgt-test",
                    "capability": "test_impact",
                    "severity": "minor",
                    "message": "Changed behavior lacks focused regression proof.",
                    "evidence": "No changed test targets src/admin.py.",
                    "path": "src/admin.py",
                },
            ]
        },
        "diff_review": {
            "blocking_findings": [],
            "major_findings": [
                {
                    "category": "risk",
                    "severity": "major",
                    "message": "Changed file is in a high-risk path.",
                    "evidence": "Workflow assurance is required.",
                    "path": ".github/workflows/proof.yml",
                }
            ],
            "minor_findings": [],
        },
        "repository_review": {
            "blocking_findings": [],
            "major_findings": [],
            "minor_findings": [],
        },
    }


def _coderabbit_comment() -> ExternalReviewComment:
    return ExternalReviewComment(
        source="live-github-review",
        body=(
            "_🎯 Functional Correctness_ | _🟡 Minor_ | _⚡ Quick win_\n\n"
            "**Naive substring severity markers misfire on common words.**\n\n"
            "The majority of reviewers may mention the word major in an example."
        ),
        repository="owner/repo",
        pr_number=10,
        path="main_review/reviewer_comparison.py",
        line=111,
        author="coderabbitai[bot]",
        url="https://example.invalid/review/1",
    )


def _reference_comments() -> list[ExternalReviewComment]:
    return [
        ExternalReviewComment(
            source="live-github-review",
            body="Potential issue: The new admin reset route has no authorization or role guard, allowing an unprivileged caller to invoke it.",
            repository="owner/repo",
            pr_number=10,
            path="src/admin.py",
            line=12,
            author="coderabbitai[bot]",
            url="https://example.invalid/review/auth",
        ),
        ExternalReviewComment(
            source="live-github-review",
            body="Nitpick: rename this local variable.",
            repository="owner/repo",
            pr_number=10,
            path="src/admin.py",
            line=4,
            author="coderabbitai[bot]",
            url="https://example.invalid/review/nit",
        ),
        ExternalReviewComment(
            source="live-github-review",
            body="## Walkthrough\nThis PR adds a reviewer comparison command.",
            repository="owner/repo",
            pr_number=10,
            author="coderabbitai[bot]",
            url="https://example.invalid/review/summary",
        ),
    ]


def test_sergeant_extraction_keeps_all_verdict_bearing_layers() -> None:
    findings = extract_sergeant_findings(_sergeant_packet())

    assert {item.finding_id for item in findings if item.finding_id.startswith("sgt-")} == {"sgt-auth", "sgt-test"}
    assert any(item.source_layer == "diff_review" and item.path == ".github/workflows/proof.yml" for item in findings)
    assert all(item.message != "Input may reach a sink." for item in findings)


def test_coderabbit_metadata_yields_real_title_severity_and_category() -> None:
    findings = extract_external_findings([_coderabbit_comment()], "CodeRabbit")

    assert len(findings) == 1
    assert findings[0].message == "Naive substring severity markers misfire on common words."
    assert findings[0].severity == "minor"
    assert findings[0].category == "correctness"


def test_word_boundaries_prevent_majority_author_and_latest_collisions() -> None:
    assert _infer_severity("The majority of reviewers agree.") == "minor"
    assert _infer_category("The author updated the latest version.") == "other"
    assert _infer_category("Authorization is missing from the route.") == "security"
    assert _infer_category("The regression test is missing.") == "testing"


def test_external_extraction_excludes_nitpicks_and_walkthroughs() -> None:
    findings = extract_external_findings(_reference_comments(), "CodeRabbit")

    assert len(findings) == 1
    assert findings[0].reviewer == "CodeRabbit"
    assert findings[0].path == "src/admin.py"
    assert findings[0].severity == "major"


def test_external_finding_id_is_stable_when_filtered_comment_order_changes() -> None:
    original = extract_external_findings([_coderabbit_comment()], "CodeRabbit")[0]
    with_earlier_nitpick = extract_external_findings([
        ExternalReviewComment(source="x", body="Nitpick: spacing", path="a.py", line=1),
        _coderabbit_comment(),
    ], "CodeRabbit")[0]

    assert original.finding_id == with_earlier_nitpick.finding_id


def test_matching_pairs_equivalent_findings_and_preserves_unique_work() -> None:
    sergeant = extract_sergeant_findings(_sergeant_packet())
    reference = extract_external_findings(_reference_comments(), "CodeRabbit")

    shared, sergeant_only, reference_only = match_findings(sergeant, reference)

    assert len(shared) == 1
    assert shared[0].sergeant.finding_id == "sgt-auth"
    assert shared[0].reference.path == "src/admin.py"
    assert shared[0].path_match is True
    assert shared[0].line_match is True
    assert any(item.finding_id == "sgt-test" for item in sergeant_only)
    assert any(item.source_layer == "diff_review" for item in sergeant_only)
    assert reference_only == []


def test_comparison_never_declares_winner_from_comment_volume() -> None:
    result = compare_reviewer_reports(
        _sergeant_packet(),
        _reference_comments(),
        reference_name="CodeRabbit",
    )

    assert result["schema_version"] == COMPARISON_SCHEMA
    assert result["counts"]["sergeant"] == 3
    assert result["counts"]["reference"] == 1
    assert result["counts"]["shared"] == 1
    assert result["winner"] is None
    assert "No winner" in result["winner_rule"]
    assert result["adjudication"]["complete"] is False


def test_adjudication_reports_verified_precision_without_inventing_recall(tmp_path: Path) -> None:
    comparison = compare_reviewer_reports(_sergeant_packet(), _reference_comments(), reference_name="CodeRabbit")
    sergeant_ids = [
        pair["sergeant"]["finding_id"] for pair in comparison["shared_findings"]
    ] + [item["finding_id"] for item in comparison["sergeant_only"]]
    reference_ids = [
        pair["reference"]["finding_id"] for pair in comparison["shared_findings"]
    ] + [item["finding_id"] for item in comparison["reference_only"]]
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({
        "decisions": [
            *[
                {"reviewer": "Sergeant", "finding_id": finding_id, "status": "confirmed"}
                for finding_id in sergeant_ids
            ],
            *[
                {"reviewer": "CodeRabbit", "finding_id": finding_id, "status": "confirmed"}
                for finding_id in reference_ids
            ],
        ]
    }), encoding="utf-8")

    result = compare_reviewer_reports(
        _sergeant_packet(),
        _reference_comments(),
        reference_name="CodeRabbit",
        adjudication_file=decisions,
    )

    assert result["adjudication"]["complete"] is True
    assert result["adjudication"]["sergeant"]["verified_precision"] == 1.0
    assert result["adjudication"]["reference"]["verified_precision"] == 1.0
    assert result["winner"] is None


def test_markdown_renders_reviewers_side_by_side_and_explicit_empty_rows() -> None:
    result = compare_reviewer_reports(_sergeant_packet(), _reference_comments(), reference_name="CodeRabbit")
    markdown = render_comparison_markdown(result)

    assert "| Metric | Sergeant | CodeRabbit |" in markdown
    assert "src/admin.py:12" in markdown
    assert "## Unique findings" in markdown
    assert "No winner is declared" in markdown

    empty = {
        "reference_name": "CodeRabbit",
        "counts": {"sergeant": 0, "reference": 0, "shared": 0, "sergeant_only": 0, "reference_only": 0},
        "shared_findings": [],
        "sergeant_only": [],
        "reference_only": [],
    }
    assert "| _None_ | _None_ |" in render_comparison_markdown(empty)
    assert "|  |  |" not in render_comparison_markdown(empty)


@dataclass(frozen=True)
class FakeLiveResult:
    pull_request: dict
    all_comments: list[dict]

    def proof_dict(self) -> dict:
        return {"proof_version": "test-proof"}


def test_live_fetch_filters_author_stale_commits_and_freezes_head(monkeypatch: pytest.MonkeyPatch) -> None:
    result = FakeLiveResult(
        pull_request={"head": {"sha": "frozen-head"}},
        all_comments=[
            {
                "body": "Potential issue: missing authorization guard.",
                "path": "src/admin.py",
                "line": 12,
                "commit_id": "frozen-head",
                "html_url": "https://example.invalid/1",
                "user": {"login": "coderabbitai[bot]"},
            },
            {
                "body": "Potential issue: stale old-head finding.",
                "path": "src/old.py",
                "line": 3,
                "commit_id": "old-head",
                "html_url": "https://example.invalid/old",
                "user": {"login": "coderabbitai[bot]"},
            },
            {
                "body": "Unrelated human comment.",
                "path": "src/admin.py",
                "line": 8,
                "commit_id": "frozen-head",
                "user": {"login": "human"},
            },
        ],
    )
    monkeypatch.setattr("main_review.reviewer_comparison.fetch_pr_comments_live", lambda *args, **kwargs: result)

    comments, metadata = load_live_external_comments(
        "owner/repo",
        10,
        author="coderabbitai",
        expected_head_sha="frozen-head",
    )

    assert len(comments) == 1
    assert comments[0].author == "coderabbitai[bot]"
    assert metadata["head_sha"] == "frozen-head"
    assert metadata["matched_author_comment_count"] == 1
    assert metadata["stale_comment_count"] == 1

    with pytest.raises(ReviewerComparisonError, match="PR head changed"):
        load_live_external_comments(
            "owner/repo",
            10,
            author="coderabbitai",
            expected_head_sha="different-head",
        )


def test_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    packet_path = tmp_path / "sergeant.json"
    packet_path.write_text(json.dumps(_sergeant_packet()), encoding="utf-8")
    review_path = tmp_path / "reference.json"
    review_path.write_text(json.dumps({
        "comments": [comment.to_dict() for comment in _reference_comments()]
    }), encoding="utf-8")
    json_output = tmp_path / "comparison.json"
    markdown_output = tmp_path / "comparison.md"

    code = main([
        "--sergeant-packet", str(packet_path),
        "--reference-review", str(review_path),
        "--reference-name", "CodeRabbit",
        "--output", str(json_output),
        "--markdown-output", str(markdown_output),
        "--pretty",
    ])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["reference_name"] == "CodeRabbit"
    assert json.loads(json_output.read_text(encoding="utf-8"))["winner"] is None
    assert "Sergeant Reviewer Comparison" in markdown_output.read_text(encoding="utf-8")


def test_cli_returns_clean_error_without_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"

    code = main([
        "--sergeant-packet", str(missing),
        "--reference-review", str(missing),
    ])

    assert code == 2
    assert "sergeant-compare:" in capsys.readouterr().err
