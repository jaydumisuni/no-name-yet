# Semantic open-model review

Sergeant combines deterministic engineering evidence with an optional semantic model council. The LLM is enabled by default in **preferred** mode, but it does not replace Main Review and it is never allowed to invent the final proof.

```text
Repository / changed files
        ↓
Deterministic Sergeant evidence
        ↓
Provider-routed semantic review
        ↓
Evidence grounding and rejection
        ↓
Optional challenger model
        ↓
Cross-source consensus
        ↓
Commander verdict
```

## What was learned from Free Claude Code

Free Claude Code (FCC) demonstrates a useful separation between the client and the model provider:

- the client speaks a stable OpenAI-compatible protocol;
- a local gateway owns provider discovery, model routing and authentication;
- different model tiers can be mapped behind one endpoint;
- clients do not need provider-specific SDKs.

Sergeant adopts that **protocol boundary**, not FCC as a hard runtime dependency. FCC currently targets a newer Python runtime than Sergeant's public package, so importing it directly would unnecessarily break compatibility. Sergeant instead talks to FCC through its local HTTP interface.

Supported routes:

| Route | Default endpoint | Protocol |
| --- | --- | --- |
| Free Claude Code | `http://127.0.0.1:8082/v1` | OpenAI Responses |
| Ollama | `http://127.0.0.1:11434/v1` | Chat Completions |
| LM Studio | `http://127.0.0.1:1234/v1` | Chat Completions |
| Explicit hosted/self-hosted endpoint | configured by owner | Responses or Chat Completions |

Automatic discovery probes **loopback endpoints only**. Sergeant never guesses a remote endpoint. Code can leave the machine only when the owner explicitly configures a remote base URL.

## Default model policy

When the endpoint exposes multiple models and no explicit model is configured, Sergeant prefers:

1. GLM-5.2
2. Qwen3-Coder-Next
3. Kimi K2.5
4. GLM-5.1
5. Qwen3-Coder
6. Kimi K2
7. the provider's first available model

This is a routing preference, not a permanent claim that one model is universally best. The owner may pin any compatible model. Model quality, latency, memory requirements, context limits and provider availability can change independently.

## Review policies

### Preferred

Default mode.

- Use semantic review when a route is available.
- Keep deterministic Sergeant evidence authoritative.
- Fall back to deterministic review when the model route is unavailable.
- State clearly in the report that the semantic pass did not run.

### Required

Strict release-gate mode.

- A semantic review must complete before Sergeant can approve.
- An unavailable or failed route produces a required action.
- Useful for high-risk release gates where the owner wants both deterministic and semantic evidence.

### Disabled

- Do not discover or call a model endpoint.
- Run deterministic Sergeant review only.

## Adaptive council

The default council mode is `adaptive`.

A second discovered model is used when:

- a primary semantic pass finds a major or blocker;
- deterministic sources disagree;
- eight or more files changed;
- CI, deployment, authentication, security, payments, database, permissions or secret-related paths changed.

The challenger is independent. Sergeant does not average unsupported opinions. Findings from either model must survive grounding before they influence consensus.

Other modes:

- `always` — use a challenger whenever another preferred model is available;
- `single` — use only the selected primary model.

## Grounding boundary

Every semantic blocker or major finding must include:

- a supplied repository path;
- a valid line range;
- evidence present in that range or file;
- a concrete impact;
- a safer correction or proof path.

Sergeant validates these fields before consensus.

- Unsupported blocker/major findings are discarded.
- Unsupported minor findings are weakened to notes.
- Files outside the supplied review scope are rejected.
- Model verdict text alone cannot override validated findings.
- Deterministic tests, runtime proof and explicit contracts outrank speculation.

This does not make review infallible. It creates a stronger, auditable gate in which every accepted high-severity semantic claim is tied back to repository evidence.

## Workspace scope

For pull requests and changed-file missions, the declared changed files are sent to the semantic reviewer.

For a full workspace mission with no changed-file list, Sergeant creates a bounded, risk-first sample. Infrastructure, configuration, database, source, UI, tests and documentation are prioritized, with high-risk paths first. Input size is limited by:

```text
SERGEANT_LLM_MAX_INPUT_CHARS
SERGEANT_LLM_MAX_FILE_CHARS
```

Binary files and paths outside the repository root are excluded.

## CLI setup

Check the resolved route:

```bash
sergeant llm-status --pretty
```

Require a route:

```bash
sergeant llm-status --require --pretty
```

Run the complete independent reviewer:

```bash
sergeant pr-review . --pretty
```

Review explicit files:

```bash
sergeant pr-review . --files "src/app.py,tests/test_app.py" --pretty
```

### FCC

Start FCC normally, then use:

```bash
export SERGEANT_LLM_PROVIDER=fcc
export SERGEANT_LLM_POLICY=preferred
export SERGEANT_LLM_PROTOCOL=responses
export SERGEANT_LLM_BASE_URL=http://127.0.0.1:8082/v1
sergeant llm-status --require --pretty
```

On PowerShell:

```powershell
$env:SERGEANT_LLM_PROVIDER = "fcc"
$env:SERGEANT_LLM_POLICY = "preferred"
$env:SERGEANT_LLM_PROTOCOL = "responses"
$env:SERGEANT_LLM_BASE_URL = "http://127.0.0.1:8082/v1"
sergeant llm-status --require --pretty
```

### Ollama

```bash
export SERGEANT_LLM_PROVIDER=ollama
export SERGEANT_LLM_MODEL=qwen3-coder-next
sergeant pr-review . --pretty
```

### LM Studio

```bash
export SERGEANT_LLM_PROVIDER=lm-studio
sergeant pr-review . --pretty
```

### Explicit OpenAI-compatible endpoint

```bash
export SERGEANT_LLM_PROVIDER=configured
export SERGEANT_LLM_BASE_URL=https://your-endpoint.example/v1
export SERGEANT_LLM_MODEL=your-model-slug
export SERGEANT_LLM_PROTOCOL=chat_completions
export SERGEANT_LLM_API_KEY=your-runtime-secret
sergeant pr-review . --pretty
```

`SERGEANT_LLM_API_KEY` is read from the process environment. It is not returned by `llm-status`, stored in the Command Center webview, written to reports, or committed to the repository.

## Configuration reference

```text
SERGEANT_LLM_ENABLED=auto|true|false
SERGEANT_LLM_POLICY=preferred|required|disabled
SERGEANT_LLM_PROVIDER=auto|fcc|ollama|lm-studio|configured
SERGEANT_LLM_BASE_URL=<explicit /v1 endpoint>
SERGEANT_LLM_MODEL=<provider model slug>
SERGEANT_LLM_PROTOCOL=auto|responses|chat_completions
SERGEANT_LLM_COUNCIL=adaptive|always|single
SERGEANT_LLM_CHALLENGER_MODEL=<optional model slug>
SERGEANT_LLM_API_KEY=<runtime secret>
SERGEANT_LLM_TIMEOUT_SECONDS=90
SERGEANT_LLM_MAX_OUTPUT_TOKENS=5000
SERGEANT_LLM_MAX_INPUT_CHARS=120000
SERGEANT_LLM_MAX_FILE_CHARS=18000
```

## IDE behavior

VS Code and JetBrains share the same Command Center controls:

- semantic policy;
- provider route;
- model slug;
- explicit base URL;
- protocol;
- council mode.

Both IDEs run workspace/current-file/changed-file review through `sergeant pr-review`. API keys remain environment-only. The single-mission gate prevents overlapping semantic and deterministic reviews from racing over report state.

## Release standard

A claim such as "complete review" means the configured gates completed and their evidence is visible. It does **not** mean that any model or static rule can guarantee zero defects.

For the strictest defensible gate:

```text
SERGEANT_LLM_POLICY=required
SERGEANT_LLM_COUNCIL=adaptive
```

Then require:

- deterministic repository review;
- diff review;
- standard verification;
- capability review;
- semantic route available;
- grounded semantic pass;
- adaptive challenger when risk triggers it;
- tests and runtime proof;
- consensus with no unanswered major or blocker.
