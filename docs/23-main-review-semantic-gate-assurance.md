# Semantic-review workflow assurance

This document records operational assurance for changes to:

- `.github/workflows/main-review.yml`
- `.github/workflows/multiplatform-proof.yml`

## Purpose

`main-review.yml` previously succeeded whenever the reviewer process executed, even when `main-review-result.json` returned `REQUEST_CHANGES`. It now makes the **actual Sergeant JSON action, consensus, and required-action list** the merge gate.

It also exposes optional semantic-review routing through repository variables and one environment secret. Semantic review remains disabled in public CI unless the repository owner explicitly configures it.

`multiplatform-proof.yml` is updated for the coordinated Sergeant `0.4.0` release. It verifies the Python and VS Code versions are `0.4.0`, the JetBrains preview is `0.4.0-preview`, builds the matching wheel/source distribution and VSIX, and uploads versioned proof artifacts. It continues to render and click the shared Command Center and inspect the JetBrains package for bundled UI resources.

## Permissions

`main-review.yml` uses:

```yaml
permissions:
  contents: read
  pull-requests: write
```

`multiplatform-proof.yml` uses:

```yaml
permissions:
  contents: read
```

Checkout uses `persist-credentials: false`. Neither workflow receives repository contents write permission, Actions write permission, release permission, package publication permission, or deployment permission.

The workflows upload artifacts and write a job summary. They do not modify source code, merge a pull request, publish a marketplace package, or execute commands supplied by pull-request text.

## Secrets

The only optional semantic credential is:

```text
SERGEANT_LLM_API_KEY
```

It is available only to `main-review.yml` through the GitHub Actions secret context. It is not copied into the generated review payload, job summary, Command Center state, repository files, or workflow artifacts.

For pull requests where secrets are unavailable, the value is empty. Semantic review is disabled by default through `SERGEANT_LLM_ENABLED=false`, so public CI does not attempt to send repository code to an external model service.

A remote model endpoint is used only when the owner explicitly configures `SERGEANT_LLM_BASE_URL`. Local FCC, Ollama and LM Studio discovery is not useful on a hosted runner unless that service is deliberately started inside the runner.

`multiplatform-proof.yml` receives no marketplace or semantic provider secret. Its FCC proof uses a local mock HTTP server created by the test suite.

## Rollback

Rollback is limited to workflow and version metadata:

1. Revert the `.github/workflows/main-review.yml` semantic environment and verdict-enforcement steps to restore artifact-only behavior.
2. Revert `.github/workflows/multiplatform-proof.yml` to the previous coordinated version and artifact names.
3. Revert `package.json`, `pyproject.toml`, and `adapters/jetbrains/gradle.properties` together if `0.4.0` is not released.
4. No database schema, customer data, deployed service, marketplace listing, or persistent runtime state is modified by these proof workflows.

The semantic reviewer modules remain independently callable and do not require either workflow integration.

## Proof

The workflow changes are accepted only when all of the following pass:

- Python tests, including provider routing, evidence grounding, hallucinated-finding rejection and required-policy behavior.
- Mock FCC `/v1/models` and `/v1/responses` HTTP integration proof.
- Main Review produces `main-review-result.json`.
- Main Review fails when `action != APPROVE`, consensus is not `PASS`, or required actions remain.
- Main Review succeeds only for `APPROVE / PASS / zero required actions`.
- The reviewer artifact remains available even when enforcement fails.
- The job summary reports semantic status and model without exposing the API key.
- Python, VS Code and JetBrains versions are coordinated as `0.4.0`, `0.4.0`, and `0.4.0-preview`.
- PyPI wheel/source validation and VSIX packaging pass.
- Browser proof passes at desktop and compact IDE widths, including semantic router persistence and duplicate-launch prevention.
- JetBrains compilation, ZIP packaging and shared-resource inspection pass.

## Data boundary

The deterministic reviewer always runs. Semantic review is additive and provider-routed. Public CI defaults to deterministic-only review because no external endpoint is implicitly trusted. This preserves the public safety boundary while allowing the repository owner to opt into a private FCC or OpenAI-compatible semantic gate later.
