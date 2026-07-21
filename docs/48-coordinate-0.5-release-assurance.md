# Sergeant 0.5.0 coordinated release assurance

## Purpose

`.github/workflows/coordinate-release.yml` creates or confirms the matching GitHub release and dispatches the existing Visual Studio Marketplace/Open VSX, PyPI, and JetBrains Marketplace publishers only after the coordinated package versions are aligned on `main`.

The 0.5.0 release packages the model-free core campaign, governed Cpl/officer review, standalone service, hardened GitHub ingestion, evidence-first reviewer comparison, proof-integrity repairs, and controlled self-learning preview described in `docs/releases/v0.5.0.md`.

## Permissions

The coordinator has only:

- `contents: write` to create the GitHub tag/release;
- `actions: write` to dispatch the existing publisher workflows.

The checkout does not persist credentials. Publisher-specific credentials remain isolated in their existing workflows and environments.

## Secrets

The coordinator does not read or contain:

- Visual Studio Marketplace or Open VSX tokens;
- JetBrains Marketplace tokens;
- PyPI passwords or API tokens;
- model-provider credentials;
- Hermes profile keys;
- Cloudflare account identifiers or API tokens.

PyPI remains tag-qualified and uses its existing trusted-publisher OIDC workflow. Model and self-learning credentials are not release inputs.

## Release boundary

Publication must occur from the exact `main` head after the stacked campaign, integrity repair, self-learning infrastructure, and release-candidate changes have been integrated. A feature-branch or stacked-PR head is not release authority.

The release workflow verifies:

- `package.json` and `pyproject.toml` both declare `0.5.0`;
- JetBrains declares `0.5.0-preview`;
- `docs/releases/v0.5.0.md` exists and is non-empty;
- the GitHub release tag is `v0.5.0`;
- duplicate registry versions are treated idempotently where supported.

The controlled-learning preview is proposal-only. Publication does not authorize automatic lesson promotion, automatic merge, or historical score rewriting.

## Rollback

Before publication, revert the release-candidate commit or close its stacked PR. After publication, published registry versions are immutable; rollback requires a new patch release that restores the prior behavior while preserving the 0.5.0 evidence and release record.

Disabling or reverting `.github/workflows/coordinate-release.yml` stops future coordinated dispatches without removing already-published artifacts.

## Proof

Before merge and publication, require the exact release-candidate head to pass:

- full CI and clean-clone proof;
- Main Review with actual-verdict enforcement;
- multiplatform proof for Python, VS Code, Command Center, and JetBrains;
- model-free campaign validation and final static holdout;
- standalone service and live GitHub ingestion proof;
- version-contract and release-workflow tests;
- credential scanning;
- external-review disposition with no unresolved actionable finding.

After publication, independently verify:

- the GitHub `v0.5.0` release and expected assets;
- Visual Studio Marketplace and Open VSX expose `0.5.0`;
- PyPI exposes both the `0.5.0` wheel and source distribution;
- the JetBrains publisher accepts or confirms `0.5.0-preview` in the preview channel;
- attached checksums match downloaded assets.

A successful coordinator run is not by itself publication verification. Each registry must be checked independently.
