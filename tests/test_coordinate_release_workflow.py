from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "coordinate-release.yml"
ASSURANCE = ROOT / "docs" / "48-coordinate-0.5-release-assurance.md"
RELEASE_NOTES = ROOT / "docs" / "releases" / "v0.5.0.md"


def test_coordinate_release_verifies_versions_and_dispatches_all_publishers() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "NPM_VERSION=$(node -p" in workflow
    assert "PYTHON_VERSION=$(python" in workflow
    assert "JETBRAINS_VERSION=$(grep '^pluginVersion='" in workflow
    assert 'test "$NPM_VERSION" = "$PYTHON_VERSION"' in workflow
    assert 'test "$JETBRAINS_VERSION" = "$NPM_VERSION-preview"' in workflow
    assert 'NOTES="docs/releases/v${NPM_VERSION}.md"' in workflow
    assert 'test -s "$NOTES"' in workflow
    assert 'echo "tag=v$NPM_VERSION"' in workflow

    assert 'gh release create "$TAG"' in workflow
    assert '--title "Sergeant v$VERSION — Model-Free Core and Governed Learning"' in workflow
    assert '--notes-file "$NOTES"' in workflow

    assert "gh workflow run publish-vscode-marketplace.yml" in workflow
    assert "gh workflow run publish-pypi.yml" in workflow
    assert '--ref "$TAG"' in workflow
    assert "gh workflow run publish-jetbrains-marketplace.yml" in workflow
    assert "PYPI_EXISTS=$(python" in workflow
    assert "sergeant-reviewer $VERSION already exists on PyPI" in workflow


def test_coordinate_release_keeps_tokens_isolated_and_checkout_uncredentialed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "persist-credentials: false" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "VSCE_PAT" not in workflow
    assert "OVSX_PAT" not in workflow
    assert "JETBRAINS_MARKETPLACE_TOKEN" not in workflow
    assert "SERGEANT_LLM_API_KEY" not in workflow
    assert "SERGEANT_HERMES_TEACHER_KEY" not in workflow


def test_coordinate_release_has_explicit_operational_assurance() -> None:
    assurance = ASSURANCE.read_text(encoding="utf-8")
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    assert ".github/workflows/coordinate-release.yml" in assurance
    for heading in ["## Purpose", "## Permissions", "## Secrets", "## Rollback", "## Proof"]:
        assert heading in assurance
    assert "v0.5.0" in assurance
    assert "published registry versions are immutable" in assurance
    assert "Visual Studio Marketplace and Open VSX expose `0.5.0`" in assurance
    assert "PyPI exposes both the `0.5.0` wheel and source distribution" in assurance
    assert "JetBrains publisher accepts or confirms `0.5.0-preview`" in assurance

    assert "# Sergeant 0.5.0 — Model-Free Core and Governed Learning" in notes
    assert "9/9 fresh blind detections" in notes
    assert "No lesson is automatically promoted" in notes
    assert "No proposal is automatically merged" in notes
