# Main Review semantic gate assurance

This document records the operational assurance for the change to `.github/workflows/main-review.yml`.

## Purpose

The workflow previously succeeded whenever the reviewer process executed, even when the generated `main-review-result.json` returned `REQUEST_CHANGES`. The change makes the **actual Sergeant JSON action, consensus, and required-action list** the merge gate.

The workflow also exposes optional semantic-review routing through repository variables and one environment secret. Semantic review remains disabled in public CI unless the repository owner explicitly configures it.

## Permissions

The workflow uses:

```yaml
permissions:
  contents: read
  pull-requests: write
```

Checkout uses `persist-credentials: false`. The reviewer does not receive repository contents write permission, Actions write permission, release permission, package permission, or deployment permission.

The current implementation uploads an artifact and writes a job summary. It does not modify source code, merge a pull request, publish a package, or execute pull-request-controlled shell commands.

## Secrets

The only optional semantic credential is:

```text
SERGEANT_LLM_API_KEY
```

It is supplied from the GitHub Actions secret context. It is not copied into the generated review payload, job summary, Command Center state, repository files, or workflow artifacts.

For pull requests where secrets are unavailable, the value is empty. Semantic review is also disabled by default through `SERGEANT_LLM_ENABLED=false`, so public CI does not attempt to send repository code to an external model service.

A remote model endpoint is used only when the repository owner explicitly configures `SERGEANT_LLM_BASE_URL`. Local FCC, Ollama and LM Studio discovery is not useful on a hosted runner unless the service is deliberately started inside that runner.

## Rollback

Rollback is a single workflow revert:

1. Revert the `.github/workflows/main-review.yml` semantic environment and verdict-enforcement steps.
2. The reviewer returns to artifact-only behavior.
3. No package data, database schema, release artifact, marketplace listing or persistent customer state is affected.

The semantic reviewer modules remain independently callable and do not require the workflow integration.

## Proof

The change is accepted only when all of the following pass:

- Python tests, including provider routing, evidence grounding, hallucinated-finding rejection and required-policy behavior.
- Mock FCC `/v1/models` and `/v1/responses` HTTP integration proof.
- Main Review produces `main-review-result.json`.
- The workflow fails when `action != APPROVE`, consensus is not `PASS`, or required actions remain.
- The workflow succeeds only for `APPROVE / PASS / zero required actions`.
- The uploaded artifact remains available even when enforcement fails.
- The job summary reports semantic status and model without exposing the API key.
- Multiplatform browser and package proof remains green.

## Data boundary

The deterministic reviewer always runs. Semantic review is additive and provider-routed. The workflow defaults to deterministic-only CI because no external endpoint is implicitly trusted. This preserves the public safety boundary while allowing the repository owner to opt into a private FCC or OpenAI-compatible semantic gate later.
