# Sergeant 0.4.1 coordinated release assurance

## Purpose

`.github/workflows/coordinate-release.yml` creates or confirms the matching GitHub release only after the coordinated package versions are aligned on the exact immutable triggering commit. First publication uses the GitHub `release: published` event to launch the Visual Studio Marketplace/Open VSX, PyPI, and JetBrains Marketplace publishers from the release tag. A retry against an existing matching release re-dispatches the same idempotent publishers from that tag.

The 0.4.1 patch publishes the useful deterministic, standalone, GitHub-ingestion, reviewer-comparison, IDE, and optional Cpl capabilities already merged after the original 0.4.0 tag. It does not import the pending adaptive self-learning stack from the 0.5.0 branches.

## Permissions

The coordinator has only:

- `contents: write` to create or verify the GitHub tag and release;
- `actions: write` to recover publisher workflows for an existing matching release.

The checkout does not persist credentials. Publisher-specific credentials remain isolated in their existing workflows and environments.

## Secrets

The coordinator does not read or contain:

- Visual Studio Marketplace or Open VSX tokens;
- JetBrains Marketplace tokens;
- PyPI passwords or API tokens;
- model-provider credentials;
- Cloudflare account identifiers or API tokens.

PyPI remains tag-qualified and uses its existing trusted-publisher OIDC workflow. Optional model configuration is not a release input.

## Release boundary

Publication must occur from the exact immutable triggering commit after the 0.4.1 release-candidate PR has passed all required proof and has been integrated into `main`. A moving branch name, feature-branch head, or later `main` revision is not release authority.

The release workflow verifies:

- checkout is pinned to `${{ github.sha }}` with complete tag history;
- `package.json` and `pyproject.toml` both declare `0.4.1`;
- JetBrains declares `0.4.1-preview`;
- `docs/releases/v0.4.1.md` exists and is non-empty;
- the GitHub release tag is `v0.4.1`;
- a mismatched existing tag is rejected rather than silently reused;
- a newly created tag resolves back to the exact triggering commit;
- first publication uses the release event once, avoiding duplicate manual dispatch;
- recovery dispatches use the immutable release tag, never the moving `main` branch;
- duplicate registry versions are treated idempotently where supported.

## Rollback

Before publication, revert the release-candidate commit or close its PR. After publication, published registry versions are immutable; rollback requires a new patch release that restores the prior behavior while preserving the 0.4.1 evidence and release record.

Disabling or reverting `.github/workflows/coordinate-release.yml` stops future coordinated dispatches without removing already-published artifacts.

## Proof

Before merge and publication, require the exact release-candidate head to pass:

- full CI and clean-clone proof;
- Main Review with actual-verdict enforcement;
- multiplatform proof for Python, VS Code, Command Center, and JetBrains;
- standalone-service and live GitHub ingestion proof;
- reviewer-intelligence and reviewer-comparison proof;
- Cloudflare connector compatibility without requiring live inference;
- coordinated version, immutable-tag, dispatch, and package tests;
- credential scanning;
- external-review disposition with no unresolved actionable finding.

After publication, independently verify:

- the GitHub `v0.4.1` tag resolves to the proven `main` release commit;
- the GitHub `v0.4.1` release and expected assets exist;
- Visual Studio Marketplace and Open VSX expose `0.4.1`;
- PyPI exposes both the `0.4.1` wheel and source distribution;
- the JetBrains publisher accepts or confirms `0.4.1-preview` in the preview channel;
- attached checksums match downloaded assets.

A successful coordinator run is not by itself publication verification. Each registry must be checked independently.
