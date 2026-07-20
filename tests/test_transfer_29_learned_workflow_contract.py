from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/model-free-core-transfer-29-learned-closure.yml")


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), "transfer-29 learned workflow must exist"
    return WORKFLOW.read_text(encoding="utf-8")


def test_transfer_29_learned_workflow_preserves_frozen_evidence_boundary() -> None:
    text = _workflow_text()

    assert "REVIEWER_SHA: 812dfbaa79a56676c8c9f008eb150585a871ca55" in text
    assert 'SERGEANT_LLM_ENABLED: "false"' in text
    assert 'SERGEANT_CPL_ENABLED: "false"' in text
    assert 'SERGEANT_CPL_POLICY: "disabled"' in text

    assert '"frozen_first_pass_run": 29778023934' in text
    assert '"frozen_first_pass_artifact": 8475444401' in text
    assert (
        '"frozen_first_pass_digest": '
        '"sha256:9736bd4c790f8d7b42e2f0d92d458d1113224834e871c1fa0df77dd2e997113a"'
        in text
    )
    assert '"classification": "learned_closure_only"' in text
    assert '"provenance_required": true' not in text.lower()


def test_transfer_29_learned_workflow_proves_controls_and_normal_pr_review() -> None:
    text = _workflow_text()

    assert "python -m pytest -q tests/test_static_transfer_29_review.py" in text
    assert "python scripts/run_static_training_set.py" in text
    assert "build/model-free-core-transfer-29-learned/runtime-manifest.json" in text
    assert "--output build/model-free-core-transfer-29-learned/frozen-result.json" in text

    assert "name: model-free-core-transfer-29-learned" in text
    assert "path: build/model-free-core-transfer-29-learned/" in text
    assert "if-no-files-found: error" in text
