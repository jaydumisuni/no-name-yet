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

Models that fail the structured contract are excluded from the focused council and reported as `probationary_models`.

Preset states are explicit:

- `fully_certified` — every configured model passed;
- `partially_certified` — at least two models passed and formed a proven council;
- `uncertified` — fewer than two models passed.

Unsupported members remain visible and are never falsely advertised as certified.

## Root-cause identity

Independent models often describe one defect with different wording, categories, or nearby line ranges. Cpl handles this in two stages:

1. A deterministic root-cause recognizer classifies well-known defect shapes such as explicit `shell=True` command execution.
2. A distance-based matcher combines reports only when they share the same normalized path, the same precise root cause, and overlapping or nearby line ranges.

The matcher does not treat every `subprocess.run` call as command injection. Explicit shell execution or command-injection language is required. Once a precise root cause exists, model-specific category wording does not split the same defect. Similar defects far apart in the same file remain separate. Unknown defect shapes retain the stricter exact category, line range, and message identity.

## Focused proof contract

The built-in fixture deliberately contains user-controlled command execution through `subprocess.run(..., shell=True)`.

The council must:

- return `BLOCK`;
- identify a `security` / `blocker` finding in `src/auth.py`;
- ground the finding in verified `evidence` containing `shell=True`;
- show support from at least two distinct certified models that actually returned matching findings in completed passes;
- complete with true model independence;
- return no provider errors or unresolved final gaps.

Claims copied into `supporting_models`, `council_confirmed_by`, messages, safer alternatives, or other prose cannot satisfy the expected-evidence or independence requirements on their own.

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

Every configured model passing upgrades the preset from partial to full certification, but it is not required for a smaller viable council to certify honestly.

## Rollback

Rollback removes:

- the viable-council summary logic from `.github/workflows/cloudflare-live-certification.yml`;
- expected-fixture arguments from `main_review/cloudflare_cli.py`;
- deterministic root-cause matching from `main_review/cpl_council.py`;
- shared finding matching from `main_review/cpl_runtime.py` and `main_review/llm_review.py`;
- focused certification-semantics tests.

Deterministic Sergeant Core, local provider routes, the existing loopback gateway, and normal pull-request CI remain operational after rollback.
