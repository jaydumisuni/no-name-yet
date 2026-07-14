# Blind Reviewer-Intelligence Proof

Sergeant's operational tests prove that the product runs safely. The blind reviewer-intelligence proof measures a different question:

```text
Does Sergeant independently find the right defects without reading the answer key or existing reviewer comments?
```

## Blindness boundary

Each benchmark case contains two separate sections:

- repository files and changed-file scope;
- expected findings used only for scoring.

The benchmark engine materializes only the repository files into a temporary workspace. Expected findings remain outside the workspace and are loaded only after `run_independent_pr_review()` returns.

Existing pull-request review comments are also excluded from live battle comparison by default. They may be included only through an explicit assisted comparison.

## Metrics

The benchmark reports:

- precision;
- recall;
- F1;
- false positives and false negatives;
- verdict accuracy;
- severity accuracy;
- affected-path accuracy;
- line localization accuracy;
- root-cause accuracy;
- duplicate rate;
- finding completeness;
- review duration;
- Cpl pass count and distinct models;
- route readiness.

Review-output completeness is not a score for the quality of the code. When Sergeant produces no ranked findings, the completeness score is reported as not evaluated rather than a misleading `100`.

## Modes

```text
sergeant-bench --mode deterministic
sergeant-bench --mode one-model --require-route
sergeant-bench --mode council --require-route
```

- `deterministic` proves the scanners, policy, intelligence and final gate without a model route.
- `one-model` measures one configured model serving bounded Cpl passes.
- `council` measures the configured multi-model Cpl council.

Model/provider configuration remains external. The public benchmark records only generic route status, model identifiers returned by the configured route, and aggregate metrics. Private provider choice and internal deployment remain outside this repository.

## Noise boundary

Repository-wide scanners remain broad, but pull-request review separates:

- findings connected to changed files;
- global credential/security blockers;
- unrelated historical background findings.

Background findings remain available to Cpl, officers and humans as context but do not dominate the current change gate.

Committed battle fixtures, expected-answer prose and project documentation are not scanned as live battle evidence. Learned rules operate on code or patch evidence, not on their own answer descriptions.

## Finding contract

A blocker or major finding reaches the Tier 2 gate only when it survives evidence challenge. Promoted findings should identify:

- what is wrong;
- the affected path and line when available;
- direct evidence;
- the triggering execution condition;
- the consequence;
- a safer alternative;
- the focused verification test.

Generic or lexical signals remain visible but are suppressed from the gate until stronger evidence exists.

## Workflow assurance

Workflow:

```text
.github/workflows/review-intelligence-proof.yml
```

- **Purpose:** run focused adversarial tests, the deterministic blind suite, installed-wheel benchmark discovery and optionally a configured one-model or council benchmark.
- **Permissions:** `contents: read` only.
- **Secrets:** optional Cpl route values are read from generic environment-backed GitHub secrets during manual runs. They are not command-line arguments or uploaded artifacts.
- **Rollback:** remove the isolated workflow and benchmark package data without changing the normal reviewer, CI, standalone service or multiplatform surfaces.
- **Proof:** benchmark JSON artifacts expose metrics and missed/extra findings while excluding credentials and expected-answer material from review input.
