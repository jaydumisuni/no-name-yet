from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "controlled-self-learning-week-1.yml"


def _job_block(workflow: str, job: str, *, next_job: str | None = None) -> str:
    marker = f"  {job}:\n"
    start = workflow.index(marker)
    if next_job is None:
        return workflow[start:]
    end = workflow.index(f"  {next_job}:\n", start + len(marker))
    return workflow[start:end]


def test_controlled_learning_targets_main_and_uses_the_active_pr_branch() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "      - main" in workflow
    assert "      - fix/coderabbit-campaign-integrity" not in workflow
    assert "TARGET_BRANCH: ${{ github.event.pull_request.head.ref }}" in workflow
    assert "AUTHORITY_HEAD: ${{ github.event.pull_request.head.sha }}" in workflow
    assert '--target-branch "${TARGET_BRANCH}"' in workflow


def test_round_authorization_precedes_and_gates_candidate_collection() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validate = _job_block(workflow, "validate", next_job="learn")

    authorize_marker = "      - name: Verify explicit owner and round authorization gates"
    collect_marker = "      - name: Collect authorized candidates or record a zero-work packet"
    assert validate.index(authorize_marker) < validate.index(collect_marker)
    assert 'index("self-learning-authorized") != null' in validate
    assert '[[ "${subject}" == START_CONTROLLED_SELF_LEARNING* ]]' in validate
    assert 'READY: ${{ steps.authorize.outputs.ready }}' in validate
    assert 'if [ "${READY}" != "true" ]; then' in validate
    assert 'collection_skipped:"round_not_authorized"' in validate
    assert 'echo "candidate_count=0" >> "$GITHUB_OUTPUT"' in validate


def test_authorized_collection_includes_governed_direct_event_signals() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validate = _job_block(workflow, "validate", next_job="learn")

    assert "--signals-dir .github/self-learning/signals" in validate
    assert "--pool-json .github/self-learning/week-1-pool.json" in validate
    assert validate.index("--signals-dir") < validate.index("--pool-json")


def test_model_free_review_and_bounded_worker_permissions_are_preserved() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    learn = _job_block(workflow, "learn", next_job="publish")

    assert 'SERGEANT_LLM_ENABLED: "false"' in workflow
    assert 'SERGEANT_CPL_ENABLED: "false"' in workflow
    assert "models: read" in learn
    assert "contents: read" in learn
    assert "contents: write" not in learn


def test_publish_job_is_a_read_only_owner_handoff() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    publish = _job_block(workflow, "publish")

    assert "name: Stage owner-controlled proposal handoff" in publish
    assert "contents: read" in publish
    assert "contents: write" not in publish
    assert "pull-requests: write" not in publish
    assert "git push" not in publish
    assert "gh pr create" not in publish
    assert "test \"$(jq -r '.automatic_promotions' \"${index}\")\" = \"0\"" in publish
    assert "test \"$(jq -r '.automatic_merges' \"${index}\")\" = \"0\"" in publish
    assert "test \"$(jq -r '.authority_head' \"${index}\")\" = \"${AUTHORITY_HEAD}\"" in publish
    assert "This workflow has no branch, pull-request, merge, or promotion authority." in publish
