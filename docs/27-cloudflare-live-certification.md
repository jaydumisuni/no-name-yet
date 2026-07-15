# Cloudflare live council certification

Assured path: `.github/workflows/cloudflare-live-certification.yml`

## Purpose

The workflow answers three questions in a controlled order:

1. Are the operator-owned Cloudflare credentials present and structurally valid?
2. Can every model in the selected public preset satisfy Sergeant's small structured-output contract?
3. Can at least two proven models complete one focused Cpl council mission with true model independence and no unresolved council gaps?

It is deliberately separate from the ten-case blind review-quality benchmark. Route certification must finish first; only certified models should be measured for precision and recall across the full suite.

## Permissions

The workflow is manual-only and declares `contents: read`. It does not request pull-request, issues, actions, deployment, package, release, or identity-token write permissions. Checkout credentials are not persisted.

## Secrets

The workflow reads only these operator-owned repository secrets:

- `SERGEANT_CLOUDFLARE_ACCOUNT_ID`
- `SERGEANT_CLOUDFLARE_API_TOKEN`

Neither value is printed by Sergeant. Every generated JSON artifact is scanned for both values before the certification verdict is allowed to pass. The workflow contains no THETECHGUY credential, account identifier, Hunter route, or private provider policy.

## Model and cost boundary

The selected preset comes from the public `main_review.cloudflare_models` registry. The same registry powers the direct Cpl route and the loopback gateway, preventing those paths from silently testing different models.

Model probes use a 320-token output ceiling. The focused council uses a 1,200-token output ceiling, at most three members, three initial passes, and two council rounds. This limits the proof surface but is not a billing guarantee; Cloudflare usage remains visible and chargeable to the operator's account under Cloudflare's current plan.

Models that fail the structured contract are excluded from the focused council. The final workflow still fails when any model in the selected preset fails, ensuring a preset cannot be advertised as certified while containing a broken member.

## Evidence

The workflow uploads:

- credential-safe route status;
- model-by-model structured proof with duration and errors;
- the exact list of models admitted to the council;
- the focused council proof;
- a compact final certification verdict.

A pass requires:

- a valid route;
- every configured model passing the structured contract;
- more than one distinct model used;
- `true_model_independence: true`;
- `council_complete: true`;
- no provider errors;
- no unresolved final gaps.

## Rollback

Rollback removes:

- `.github/workflows/cloudflare-live-certification.yml`;
- `docs/27-cloudflare-live-certification.md`;
- the shared roster/redaction changes in `main_review/cloudflare_models.py`;
- the gateway adoption of that shared roster;
- the live-proof output limits and timing metadata;
- the focused roster tests.

Deterministic Sergeant Core, local provider routes, the existing loopback gateway, and normal pull-request CI remain operational after rollback.
