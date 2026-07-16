# Full Cloudflare council certification assurance

Assured path: `.github/workflows/cloudflare-full-council-certification.yml`

## Purpose

The workflow performs the exact-head live admission proof for every unique
Cloudflare Workers AI member in Sergeant's public council roster. It separates
transport compatibility from role capability:

- all seven members must satisfy the bounded structured-output contract;
- six reasoning and coding members must complete the evidence-grounded security
  officer mission;
- Granite 4.0 H Micro must complete a role-appropriate Scout evidence-extraction
  mission with exact values, file coverage and line evidence.

The workflow is a certification gate. It does not review arbitrary repositories,
run pull-request-controlled project code, apply patches, publish releases or grant
models any repository authority.

## Permissions

The workflow declares only `contents: read`.

Checkout uses `persist-credentials: false`, so the GitHub token is not retained in
the repository configuration. The workflow cannot push commits, create comments,
modify pull requests, dispatch deployments, publish packages or merge changes.

Every model call is initiated by Sergeant's allowlisted Cloudflare connector. The
models receive bounded fixture text and cannot invoke shell commands, network tools
or repository writes.

## Secrets

The live proof reads these operator-owned GitHub Actions secrets:

- `SERGEANT_CLOUDFLARE_ACCOUNT_ID`;
- `SERGEANT_CLOUDFLARE_API_TOKEN`.

They are used only to construct the Cloudflare Workers AI route. They are never
written to Git, passed as command-line arguments or copied into the public summary.
Before artifact upload, the workflow scans every JSON proof file for both configured
secret values. Evidence upload is allowed only when that scan succeeds.

Public status output masks the Account ID and reports credential presence as
booleans. A provider quota refusal remains a failed external proof and cannot be
represented as a model certification result.

## Rollback

Rollback removes:

- `.github/workflows/cloudflare-full-council-certification.yml`;
- `main_review/cloudflare_scout_qualification.py`;
- the full-roster compatibility additions in `main_review/cloudflare_cli.py`,
  `main_review/cloudflare_models.py` and `main_review/llm_provider.py`;
- `tests/test_cloudflare_full_roster_qualification.py`;
- the Qwen2.5 proof-budget expectation in
  `tests/test_cloudflare_native_fallback.py`;
- this assurance document.

The two-member mission-qualified baseline, deterministic Sergeant Core, permanent
officers, provider-neutral Cpl routing and all non-Cloudflare routes remain usable
after rollback.

## Proof

The change is acceptable only when all of the following are true on the same exact
candidate head:

1. focused compatibility and mission-qualification tests pass;
2. the complete repository test suite passes;
3. normal CI, Main Review, Review Intelligence, Reviewer Comparison, Live GitHub
   Ingestion, Standalone Service, Cloudflare Connector and Multiplatform proofs pass;
4. the Cloudflare route validates without exposing credentials;
5. structured transport passes for seven of seven configured members;
6. the six reasoning/coding members pass the complete officer mission;
7. Granite passes the grounded Scout evidence-extraction mission;
8. the final certified roster contains all seven unique members;
9. the credential scan succeeds before artifact upload;
10. the artifact records the exact tested commit and contains no configured secret.

The workflow remains red when Cloudflare's daily allocation is exhausted. Quota
blocking proves neither model success nor model failure; the exact-head proof must be
rerun after the provider resets the allocation.

## Operational cost boundary

The proof uses the operator's own Cloudflare allocation. It is intentionally
manual in lifecycle even though the pull-request workflow records exact-head changes.
The branch is frozen before the meaningful retry, and failed quota runs are not
looped continuously. The seven-member live proof is required only for roster or
certification-contract changes, not for ordinary Sergeant pull requests.
