# Coordinated 0.4.0 release assurance

This document records the operational assurance for the change to `.github/workflows/coordinate-release.yml`.

## Purpose

The coordinator creates or confirms the `v0.4.0` GitHub release after verifying that:

- `package.json` is `0.4.0`;
- `pyproject.toml` is `0.4.0`;
- the JetBrains plugin is `0.4.0-preview`.

It then dispatches the existing marketplace publishers for Visual Studio Marketplace, Open VSX, PyPI, and the JetBrains Marketplace preview channel. The release notes are updated to describe the semantic open-model reviewer rather than the earlier 0.3 Command Center release.

## Permissions

The workflow uses:

```yaml
permissions:
  contents: write
  actions: write
```

`contents: write` is needed only to create the Git tag/release and attach publisher artifacts. `actions: write` is needed only to dispatch the existing publication workflows.

Checkout uses `persist-credentials: false`. The workflow does not modify source code, merge pull requests, change repository settings, or obtain deployment administration permission.

## Secrets

The coordinator receives only `github.token`. It does not receive marketplace tokens or the semantic-review API key.

Marketplace credentials remain isolated in their dedicated publisher workflows:

- `VSCE_PAT` and `OVSX_PAT` in the VS Code publisher;
- PyPI trusted publishing through GitHub OIDC and the protected `pypi` environment;
- `JETBRAINS_MARKETPLACE_TOKEN` in the JetBrains publisher.

The coordinator checks PyPI's public JSON endpoint before dispatching a new trusted publication. Missing PyPI versions are dispatched from the matching `v*` tag because the `pypi` environment permits release tags only.

## Rollback

Before publication, rollback is a normal commit revert.

After publication:

- published registry versions are immutable and must not be overwritten;
- a faulty release must be corrected with a new patch version;
- the GitHub release can be annotated or marked as superseded, but package files already accepted by registries remain historical artifacts;
- the coordinator can be reverted without altering installed copies.

## Proof

The change is accepted only when:

- Sergeant Main Review returns `APPROVE` with consensus `PASS` and no required actions;
- CI and clean-clone proof pass;
- the coordinator validates the three coordinated version values;
- the GitHub release is created or confirmed;
- each publisher workflow is dispatched with `v0.4.0`;
- Visual Studio Marketplace and Open VSX expose `0.4.0`;
- PyPI exposes both the `0.4.0` wheel and source distribution;
- the JetBrains publisher accepts or confirms `0.4.0-preview` in the preview channel;
- GitHub release assets include the VSIX, Python distributions, JetBrains ZIP, and checksums.

## Data boundary

The workflow publishes already-reviewed source artifacts. It does not run a remote semantic model, transmit repository code to a model provider, or expose `SERGEANT_LLM_API_KEY`. Semantic routing remains a runtime feature of Sergeant and is separate from package publication.
