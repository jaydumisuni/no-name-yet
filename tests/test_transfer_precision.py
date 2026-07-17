from __future__ import annotations

from pathlib import Path

from main_review.capability_policy import normalize_capability_review
from main_review.officer_council import _adjudicate, _normalize


def test_generic_source_sink_messages_are_advisory_not_actionable() -> None:
    candidates = [
        _normalize(
            {
                "capability": "security_taint",
                "severity": "major",
                "path": "src/large_handler.py",
                "line_start": 10,
                "evidence_ref": "src/large_handler.py:10",
                "direct_evidence": True,
                "root_cause": "unsafe-data-flow",
                "message": "Potential tainted input path needs validation review.",
                "evidence": "Input and sink terms coexist in a large file.",
            },
            "capability",
        ),
        _normalize(
            {
                "capability": "data_flow",
                "severity": "major",
                "path": "src/large_handler.py",
                "line_start": 10,
                "evidence_ref": "src/large_handler.py:10",
                "direct_evidence": True,
                "root_cause": "unsafe-data-flow",
                "message": "User-controlled input appears near a risky sink.",
                "evidence": "Input and sink terms coexist in a large file.",
            },
            "capability",
        ),
    ]

    admitted, advisory, rejected = _adjudicate(candidates, {"promoted_findings": []})

    assert admitted == []
    assert rejected == []
    assert len(advisory) == 2
    assert all(item["admission"] == "risk_trigger" for item in advisory)
    assert all(item["gates_verdict"] is False for item in advisory)


def test_unrelated_request_and_fixed_file_functions_do_not_form_path_flow(tmp_path: Path) -> None:
    source = tmp_path / "pipeline.py"
    source.write_text(
        """
def parse_request(request):
    return request.args.get("mode")


def load_internal_template():
    return open("/srv/templates/default.md", "r", encoding="utf-8").read()
        """,
        encoding="utf-8",
    )

    normalized = normalize_capability_review(
        {
            "verdict": "PASS",
            "changed_files": [source.name],
            "findings": [],
        },
        tmp_path,
    )

    assert not any(
        item.get("root_cause") == "unsafe-file-access"
        for item in normalized["findings"]
    )
    assert normalized["verdict"] == "PASS"


def test_same_function_request_path_to_open_remains_grounded(tmp_path: Path) -> None:
    source = tmp_path / "download.py"
    source.write_text(
        """
def download(request):
    name = request.args.get("name")
    return open("/srv/files/" + name, "rb")
        """,
        encoding="utf-8",
    )

    normalized = normalize_capability_review(
        {
            "verdict": "PASS",
            "changed_files": [source.name],
            "findings": [],
        },
        tmp_path,
    )

    roots = {item.get("root_cause") for item in normalized["findings"]}
    assert "unsafe-file-access" in roots
    assert normalized["verdict"] == "NEEDS WORK"
