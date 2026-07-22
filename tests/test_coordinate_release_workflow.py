from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "coordinate-release.yml"
ASSURANCE = ROOT / "docs" / "49-coordinate-0.4.1-release-assurance.md"
NOTES = ROOT / "docs" / "releases" / "v0.4.1.md"


def _step_block(workflow: str, name: str, *, next_name: str | None = None) -> str:
    marker = f"      - name: {name}\n"
    start = workflow.index(marker)
    if next_name is None:
        return workflow[start:]
    end = workflow.index(f"      - name: {next_name}\n", start + len(marker))
    return workflow[start:end]


def test_coordinate_release_verifies_versions_and_pins_one_release_identity() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    metadata = _step_block(
        workflow,
        "Verify coordinated versions and release notes",
        next_name="Create or confirm commit-bound GitHub release",
    )
    release = _step_block(
        workflow,
        "Create or confirm commit-bound GitHub release",
        next_name="Recover publishers for an existing matching release",
    )

    assert "NPM_VERSION=$(node -p" in metadata
    assert "PYTHON_VERSION=$(python" in metadata
    assert "JETBRAINS_VERSION=$(grep '^pluginVersion='" in metadata
    assert 'NOTES="docs/releases/v${NPM_VERSION}.md"' in metadata
    assert 'test "$NPM_VERSION" = "$PYTHON_VERSION"' in metadata
    assert 'test "$JETBRAINS_VERSION" = "$NPM_VERSION-preview"' in metadata
    assert 'test -s "$NOTES"' in metadata
    assert 'echo "tag=v$NPM_VERSION" >> "$GITHUB_OUTPUT"' in metadata
    assert 'echo "release_sha=$GITHUB_SHA" >> "$GITHUB_OUTPUT"' in metadata

    assert "Check out immutable release commit" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "fetch-depth: 0" in workflow
    assert "RELEASE_SHA: ${{ steps.metadata.outputs.release_sha }}" in release
    assert 'test "$TAG_SHA" = "$RELEASE_SHA"' in release
    assert '--target "$RELEASE_SHA"' in release
    assert 'test "$CREATED_TAG_SHA" = "$RELEASE_SHA"' in release
    assert "--target main" not in workflow
    assert "--ref main" not in workflow


def test_existing_tag_must_match_the_proven_commit() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    release = _step_block(
        workflow,
        "Create or confirm commit-bound GitHub release",
        next_name="Recover publishers for an existing matching release",
    )

    assert 'git show-ref --tags --verify --quiet "refs/tags/$TAG"' in release
    assert 'TAG_SHA=$(git rev-list -n 1 "$TAG")' in release
    assert 'test "$TAG_SHA" = "$RELEASE_SHA"' in release
    assert "Existing tag $TAG points to $TAG_SHA, expected proven commit $RELEASE_SHA." in release
    assert "Release $TAG exists without a resolvable matching tag." in release
    assert "--verify-tag" in release
    assert 'CREATED_TAG_SHA=$(git rev-list -n 1 "$TAG")' in release
    assert 'test "$CREATED_TAG_SHA" = "$RELEASE_SHA"' in release


def test_new_release_uses_release_event_and_existing_release_recovers_from_tag() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    release = _step_block(
        workflow,
        "Create or confirm commit-bound GitHub release",
        next_name="Recover publishers for an existing matching release",
    )
    recovery = _step_block(
        workflow,
        "Recover publishers for an existing matching release",
        next_name="Confirm first-publication dispatch path",
    )
    first_publication = _step_block(workflow, "Confirm first-publication dispatch path")

    assert 'gh release create "$TAG"' in release
    assert '--title "Sergeant v$VERSION — Useful Model-Free Baseline"' in release
    assert '--notes-file "$NOTES"' in release
    assert "if: steps.release.outputs.created == 'false'" in recovery
    assert "if: steps.release.outputs.created == 'true'" in first_publication

    for publisher in (
        "publish-vscode-marketplace.yml",
        "publish-pypi.yml",
        "publish-jetbrains-marketplace.yml",
    ):
        command_start = recovery.index(f"gh workflow run {publisher}")
        command_end = recovery.find("\n\n", command_start)
        command = recovery[command_start : command_end if command_end != -1 else None]
        assert '--repo "$GITHUB_REPOSITORY"' in command
        assert '--ref "$TAG"' in command
        assert '--field release_tag="$TAG"' in command

    assert "release:published event dispatches all three publishers" in first_publication
    assert "duplicate manual dispatch is intentionally skipped" in first_publication


def test_coordinate_release_keeps_tokens_isolated_and_checkout_uncredentialed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "persist-credentials: false" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "VSCE_PAT" not in workflow
    assert "OVSX_PAT" not in workflow
    assert "JETBRAINS_MARKETPLACE_TOKEN" not in workflow
    assert "SERGEANT_CPL_API_KEY" not in workflow
    assert "SERGEANT_LLM_API_KEY" not in workflow


def test_coordinate_release_has_explicit_operational_assurance_and_notes() -> None:
    assurance = ASSURANCE.read_text(encoding="utf-8")
    notes = NOTES.read_text(encoding="utf-8")

    assert ".github/workflows/coordinate-release.yml" in assurance
    for heading in ["## Purpose", "## Permissions", "## Secrets", "## Rollback", "## Proof"]:
        assert heading in assurance
    assert "v0.4.1" in assurance
    assert "immutable triggering commit" in assurance
    assert "mismatched existing tag" in assurance
    assert "published registry versions are immutable" in assurance
    assert "Visual Studio Marketplace and Open VSX expose `0.4.1`" in assurance
    assert "PyPI exposes both the `0.4.1` wheel and source distribution" in assurance
    assert "JetBrains publisher accepts or confirms `0.4.1-preview`" in assurance

    assert "# Sergeant 0.4.1 — Useful Model-Free Baseline" in notes
    assert "Useful without an AI account" in notes
    assert "does not include the adaptive self-learning queue" in notes
