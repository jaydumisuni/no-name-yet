# Cloudflare connector workflow assurance

Assured path: `.github/workflows/cloudflare-connector-proof.yml`

## Purpose

The workflow proves the public Cloudflare connector without contacting a live
provider or requiring private credentials. It runs focused gateway tests,
credential-redaction checks, source packaging and installed-wheel execution.

## Permissions

The workflow declares `contents: read`. It does not request pull-request write,
issues write, actions write, deployments write, packages write or identity-token
permissions. It does not publish releases or mutate repository state.

The checkout step sets `persist-credentials: false`, so the GitHub token is not
left in the checked-out repository configuration for later build or test steps.

## Secrets

The pull-request workflow receives no Cloudflare Account ID or API token. The
proof intentionally checks behavior when credentials are absent and verifies
that public status output contains only boolean presence indicators. Live
Workers AI tests are performed separately with operator-owned secrets stored
outside Git and outside public workflow logs.

The first public gateway release is loopback-only. It does not offer a remote
bind option that could expose the operator's Cloudflare quota or billing account
through an unauthenticated network endpoint.

## Rollback

Rollback removes:

- `.github/workflows/cloudflare-connector-proof.yml`;
- `main_review/cloudflare_gateway.py`;
- `main_review/cloudflare_cli.py`;
- the `sergeant-cloudflare` package entrypoint;
- Cloudflare-specific tests and documentation.

Deterministic Sergeant Core, existing Cpl routes and all other workflows remain
operational after rollback.

## Proof

Required proof is:

1. focused `tests/test_cloudflare_gateway.py` passes;
2. missing-credential status exits with the required failure code;
3. no token value appears in status artifacts;
4. unsupported models, streaming and malformed chat payloads fail as client
   errors without reaching Cloudflare;
5. structured model proof validates every required field;
6. council certification rejects errors, unresolved gaps or incomplete councils;
7. source and wheel packages build;
8. the installed wheel exposes `sergeant-cloudflare`;
9. existing Sergeant CI, Main Review, standalone, intelligence, ingestion and
   multiplatform workflows remain green.

A separate live certification is required before claiming that a Cloudflare
reasoning council is operational. That certification must record multiple real
model calls, a complete council, no provider errors, no final gaps and
`true_model_independence: true` without exposing secrets.
