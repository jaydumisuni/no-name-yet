# Cloudflare Workers AI council

Sergeant can use Cloudflare Workers AI through its OpenAI-compatible endpoint. The connector is optional and provider credentials remain outside the repository.

## Required environment

```bash
export SERGEANT_CPL_PROVIDER=cloudflare
export SERGEANT_CLOUDFLARE_ACCOUNT_ID=your_account_id
export SERGEANT_CLOUDFLARE_API_TOKEN=your_scoped_workers_ai_token
export SERGEANT_CPL_POLICY=required
```

Sergeant derives the endpoint:

```text
https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1
```

The Account ID is masked in reports. The token is never included in public settings or proof artifacts.

## Default roster

`cloudflare-free-balanced` is selected when no model or roster is supplied:

1. `@cf/qwen/qwen3-30b-a3b-fp8` — efficient general reasoning.
2. `@cf/zai-org/glm-4.7-flash` — independent challenger.
3. `@cf/openai/gpt-oss-20b` — stronger specialist/adjudication pass.
4. `@cf/qwen/qwen2.5-coder-32b-instruct` — narrow coding specialist.

The order is intentional. Expensive specialists are recruited only after broad passes leave an evidence gap.

Other built-in presets:

```bash
export SERGEANT_CPL_MODEL_PRESET=cloudflare-free-efficient
export SERGEANT_CPL_MODEL_PRESET=cloudflare-free-strong
```

An exact user roster always wins:

```bash
export SERGEANT_CPL_MODELS='@cf/qwen/qwen3-30b-a3b-fp8,@cf/zai-org/glm-4.7-flash'
```

## Free-allocation guardrails

Cloudflare currently includes 10,000 neurons per day on Workers Free. Sergeant therefore uses a lower Cloudflare output default of 1,800 tokens. A conservative starting configuration is:

```bash
export SERGEANT_CPL_DEPTH=adaptive
export SERGEANT_CPL_MAX_PASSES=3
export SERGEANT_CPL_MAX_COUNCIL_MEMBERS=3
export SERGEANT_CPL_MAX_ROUNDS=3
export SERGEANT_CPL_MAX_OUTPUT_TOKENS=1200
export SERGEANT_CPL_MAX_INPUT_CHARS=30000
```

These are review limits, not billing guarantees. Monitor Workers AI usage in Cloudflare and keep the account on Workers Free if hard no-charge behavior is required.

## Proof workflow assurance

The high-risk workflow changed by this feature is `.github/workflows/review-intelligence-proof.yml`.

- **Purpose:** run deterministic proof on every PR and allow an explicit manual one-model or council benchmark.
- **Permissions:** the workflow remains read-only with `contents: read`; checkout credentials are not persisted.
- **Secrets:** Cloudflare and generic provider credentials are accepted only through GitHub Actions secrets and are scanned out of generated artifacts.
- **Rollback:** remove the Cloudflare secrets or dispatch deterministic mode; the existing local and OpenAI-compatible routes remain unchanged.
- **Proof:** focused connector tests, route-required status, the blind benchmark, installed-wheel proof, and artifact secret scanning must all pass.

## Prove the route

```bash
sergeant cpl-status --require
sergeant-bench review-benchmarks/blind \
  --mode council \
  --require-route \
  --minimum-precision 0.90 \
  --minimum-recall 0.90 \
  --pretty
```

A valid council proof must show multiple distinct models, a completed council, no unresolved required gaps, and benchmark quality above the configured thresholds.

## Generic provider compatibility

Cloudflare support does not make Sergeant Cloudflare-dependent. Users can continue to configure Ollama, LM Studio, a local Cpl gateway, or any OpenAI-compatible endpoint. `SERGEANT_CPL_MODELS` also works with those routes when the endpoint does not expose a model-list API.
