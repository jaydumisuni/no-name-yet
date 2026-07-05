from __future__ import annotations

from pathlib import Path

from main_review.app_bridge import handle_app_review_request
from main_review.evidence_consensus import build_evidence_consensus


def test_evidence_consensus_classifies_external_findings() -> None:
    internal_packet = {
        "review_intelligence": {
            "ranked_findings": [
                {
                    "capability": "api_contract",
                    "severity": "major",
                    "message": "Client route has no matching server route.",
                    "evidence": "fetch('/missing') was found.",
                    "confidence": 0.7,
                    "path": "src/client.js",
                }
            ]
        }
    }
    external = [
        {
            "source": "CodeRabbit",
            "verdict": "NEEDS WORK",
            "evidence": [
                {
                    "message": "Client route has no matching server route.",
                    "evidence": "CodeRabbit saw same route drift.",
                    "path": "src/client.js",
                    "confidence": 0.75,
                }
            ],
        },
        {
            "source": "Semgrep",
            "verdict": "PASS",
            "message": "No Semgrep findings.",
        },
    ]

    result = build_evidence_consensus(internal_packet, external)

    assert result["verdict"] == "NEEDS WORK"
    assert result["summary"]["external_sources"] == ["CodeRabbit", "Semgrep"]
    assert any(item["classification"] == "correct" for item in result["classified_findings"])
    assert result["rule"].startswith("Sergeant owns")


def _make_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "main_review").mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def ok():\n    return True\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (root / "docs").mkdir()
    for name in [
        "12-external-review-learning-loop.md",
        "19-thetechguy-engineering-standard.md",
        "20-clean-clone-proof.md",
        "21-open-source-reviewer-patterns.md",
    ]:
        (root / "docs" / name).write_text("# Doc\n", encoding="utf-8")


def test_app_bridge_returns_evidence_consensus(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = handle_app_review_request(
        {
            "root": str(tmp_path),
            "mode": "pull_request",
            "changed_files": ["src/app.py", "tests/test_app.py"],
            "external_providers": [{"source": "CodeRabbit", "verdict": "PASS", "message": "No concerns."}],
        }
    )

    assert payload["ok"] is True
    assert "evidence_consensus" in payload
    assert payload["evidence_consensus"]["summary"]["external_sources"] == ["CodeRabbit"]
