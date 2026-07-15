# Cloudflare live council certification

Assured path: `.github/workflows/cloudflare-live-certification.yml`

## Purpose

The workflow answers four questions in a controlled order:

1. Are the operator-owned Cloudflare credentials present and structurally valid?
2. Which models in the selected public preset satisfy Sergeant's structured-output contract?
3. Are at least two proven models available to form a genuinely independent council?
4. Can that council inspect a focused fixture, return the expected verdict, and independently support the expected grounded defect?

It is deliberately separate from the ten-case blind review-quality benchmark. Route and council certification must finish first; only certified models should be measured for precision and recall across the full suite.

## Permissions

The workflow is manual-only and declares `contents: read`. It does not request pull-request, issues, actions, deployment, package, release, or identity-token write permissions. Checkout credentials are not persisted.

## Secrets

The workflow reads only these operator-owned repository secrets:

- `SERGEANT_CLOUDFLARE_ACCOUNT_ID`
- `SERGEANT_CLOUDFLARE_API_TOKEN`

Neither value is printed by Sergeant. Every generated JSON artifact is scanned for both values before evidence upload is allowed. The workflow contains no THETECHGUY credential, account identifier, Hunter route, or private provider policy.

## Model and cost boundary

The selected preset comes from the public `main_review.cloudflare_models` registry. The same registry powers the direct Cpl route and the loopback gateway, preventing those paths from silently testing different models.

Ordinary model probes use a 384-token output ceiling. Known reasoning models use a bounded 900-token proof budget. The focused council uses a 1,200-token output ceiling, at most three members, three initial passes, and two council rounds. These limits reduce proof cost but are not billing guarantees; Cloudflare usage remains visible and chargeable to the operator's account under Cloudflare's current plan.

Models that fail the structured contract are excluded from the focused council and reported as `probationary_models`. A preset can therefore be `partially_certified` when at least two models form a proven council, while unsupported members remain visible and are never falsely advertised as certified.

## Root-cause identity

Independent models often describe one defect with different wording or line ranges. Cpl now groups recognized defect shapes by:

- normalized path;
- category;
- deterministic root-cause class;
- nearby ten-line source window.

This allows Analyst to combine support for one underlying defect without merging similar defects that occur far apart in the same file. Unknown defect shapes retain the stricter exact line-and-message identity.

## Focused proof contract

The built-in fixture deliberately contains user-controlled command execution through `subprocess.run(..., shell=True)`.

The council must:

- return `BLOCK`;
- identify a `security` / `blocker` finding in `src/auth.py`;
- ground the finding in `shell=True` evidence;
- show support from at least two distinct certified models;
- complete with true model independence;
- return no provider errors or unresolved final gaps.

A correct `BLOCK` is proof of reviewer capability, not a certification failure.

## Evidence

The workflow uploads:

- credential-safe route status;
- model-by-model structured proof with duration and errors;
- the exact certified model list;
- probationary model results;
- the focused council proof and expected-finding match;
- a compact final certification verdict.

A pass requires:

- a valid route;
- at least two structured-contract-certified models;
- the expected `BLOCK` verdict;
- the expected independently supported blocker;
- more than one distinct model used;
- `true_model_independence: true`;
- `council_complete: true`;
- no provider errors;
- no unresolved final gaps.

Every configured model passing is reported as `fully_certified`, but it is not required for a smaller viable council to certify honestly.

## Rollback

Rollback removes:

- the viable-council summary logic from `.github/workflows/cloudflare-live-certification.yml`;
- expected-fixture arguments from `main_review/cloudflare_cli.py`;
- deterministic root-cause identity from `main_review/cpl_council.py`;
- shared finding identity use from `main_review/llm_review.py`;
- focused certification-semantics tests.

Deterministic Sergeant Core, local provider routes, the existing loopback gateway, and normal pull-request CI remain operational after rollback.
