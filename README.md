<p align="center">
  <img src="resources/readme-top-image.png" alt="Sergeant - open-source engineering reviewer" width="960">
</p>

# Sergeant

**Sergeant (SRG)** is an open-source software engineering review system created by **THETECHGUY DIGITAL SOLUTIONS**.

Sergeant inspects repositories, reviews pull requests, verifies engineering standards, and produces evidence-based reports. It is not a one-shot coding assistant. It is the reviewer that challenges assumptions, checks proof, and reports what remains before merge or release.

```text
PASS
NEEDS WORK
BLOCK
```

## Review architecture

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

Main Review remains the reviewer core. An LLM is an independent evidence source, not the final authority.

Every accepted semantic blocker or major finding must identify a supplied repository path, a valid line range, and supporting source text. Unsupported high-severity claims are discarded before consensus. Deterministic tests, runtime proof and explicit contracts outrank model speculation.

This creates a stronger, auditable gate. It does not claim that any model or static rule can guarantee zero defects.

## Who Sergeant is for

- Individual developers who want a second engineering review before shipping.
- Open-source maintainers reviewing pull requests and project changes.
- Teams that care about standards, evidence, and repeatable review flow.
- AI-assisted development workflows where generated code still needs independent review.
- Self-hosted or model-agnostic environments that should not depend on one provider.

## Core principles

- **Evidence before opinion.**
- **Standards before assumptions.**
- **Review before merge.**
- **Verification before release.**
- **Human judgment remains final.**
- **Finish, then prove.**
- **Claims must match implementation.**

## FCC-compatible provider routing

Sergeant adopts the protocol architecture demonstrated by **Free Claude Code (FCC)** without importing FCC as a hard Python dependency. Sergeant can talk to FCC through its local OpenAI Responses endpoint while preserving Python 3.10+ compatibility.

Supported routes:

| Route | Default endpoint | Protocol |
| --- | --- | --- |
| Free Claude Code | `http://127.0.0.1:8082/v1` | OpenAI Responses |
| Ollama | `http://127.0.0.1:11434/v1` | Chat Completions |
| LM Studio | `http://127.0.0.1:1234/v1` | Chat Completions |
| Explicit hosted/self-hosted endpoint | owner configured | Responses or Chat Completions |

Automatic discovery probes loopback endpoints only. Sergeant never guesses a remote service. Code can leave the machine only when an owner explicitly configures a remote base URL.

When multiple models are exposed and no model is pinned, Sergeant prefers:

1. GLM-5.2
2. Qwen3-Coder-Next
3. Kimi K2.5
4. GLM-5.1
5. Qwen3-Coder
6. Kimi K2
7. provider fallback

The preference is configurable and is not a permanent claim that one model is universally best.

### Semantic policies

**Preferred** is the product default:

- use semantic review when a route is available;
- fall back to deterministic Sergeant evidence when it is not;
- state clearly in the report whether the semantic pass ran.

**Required** is the strict release gate:

- no approval when the semantic route is unavailable or fails;
- all required deterministic and semantic evidence must complete.

**Disabled** runs deterministic review only.

### Adaptive model council

The default council mode is `adaptive`. A second discovered model is used for high-risk paths, large changes, primary-model major findings, or disagreement among deterministic sources.

Other modes:

- `always` — use a challenger whenever another preferred model is available;
- `single` — use only the selected primary model.

Full setup, privacy, grounding and configuration details are in [`docs/22-semantic-open-model-review.md`](docs/22-semantic-open-model-review.md).

## Engineering workflow

```text
Understand
    ↓
Review
    ↓
Challenge
    ↓
Verify
    ↓
Freeze
    ↓
Prove
    ↓
Ship
```

## Sergeant V2 Command Center

```text
Commander
    ↓
Mission
    ↓
Officers
    ↓
Weapon Manifest
    ↓
Deterministic Evidence
    ↓
Semantic Evidence
    ↓
Verification
    ↓
Commander Verdict
    ↓
Audit Trail
```

The VS Code extension provides a compact activity-bar launcher and a full editor Command Center. The JetBrains preview uses the same interface through JCEF and falls back to a native Swing panel when JCEF is unavailable.

The interface includes:

- Commander dashboard and live workspace state.
- Mission Planner for repository, changed-file, release, battle, final-proof, IDE and custom missions.
- Semantic router controls for policy, provider, model, base URL, protocol and council mode.
- Live mission progress and evidence.
- Evidence views for static, runtime, semantic, UI, documentation, battle and optional external review.
- Evidence Locker with report history, open, copy, export and refresh actions.
- Officer deployment and armoury views.
- Settings, Review Doctrine, Post-V2 Roadmap and Guide pages.
- One-active-mission gates in both VS Code and JetBrains.

### Writer safety boundary

- Disabled by default.
- Draft patches only.
- Human approval required.
- Never auto-merge.

## Current capability set

### Repository and engineering review

- Repository inspection and understanding.
- Pull-request, current-file and changed-file review.
- Architecture and regression-risk checks.
- Static analysis and security signals.
- Documentation drift checks.
- Evidence consensus and standards verification.
- Evidence-grounded semantic review.
- Adaptive open-model challenger review.
- Verified learning and squad-style review intelligence.

### Developer workflow

- CLI review flow.
- App bridge contract.
- IDE Bench contract for VS Code, PyCharm, JetBrains and AI handoff.
- Full VS Code Command Center.
- JetBrains Command Center preview.
- Read-only GitHub PR comment ingestion.
- Live GitHub review bridge.
- FCC, Ollama, LM Studio and explicit OpenAI-compatible routes.

### Proof and battle validation

- Battle-test fixtures and validator.
- Static review-signal comparison.
- Live PR patch fetch for battle comparison.
- CI and clean-clone proof.
- Browser-rendered Command Center proof at desktop and compact IDE widths.
- Semantic router and duplicate-launch browser proof.
- Mock FCC Responses wire-contract proof.
- PyPI wheel/source validation, VSIX packaging and JetBrains plugin packaging.

## Installation

### Python / CLI

Published stable package:

```bash
python -m pip install sergeant-reviewer==0.4.0
```

Current source development:

```bash
git clone https://github.com/jaydumisuni/Sergeant.git
cd Sergeant
python -m pip install -e .
```

Requires Python 3.10 or newer.

### VS Code

Install Sergeant from the Visual Studio Marketplace or Open VSX. For a local package:

```bash
npx @vscode/vsce package --no-dependencies
code --install-extension sergeant-reviewer-0.4.0.vsix --force
```

Open **Sergeant** from the activity bar, then use **Open Full Command Center**.

### JetBrains IDEs

The current marketplace preview targets the 2025.2 / build 252 line. Install the Sergeant CLI first:

```bash
python -m pip install sergeant-reviewer==0.4.0
```

Set `SERGEANT_CLI` when the executable is not on the IDE process path.

## Quick start

### Deterministic-only review

```bash
sergeant review . --pretty
```

### Complete independent review

The full reviewer uses deterministic evidence and semantic review when available:

```bash
sergeant pr-review . --pretty
```

Review explicit files:

```bash
sergeant pr-review . --files "src/app.py,tests/test_app.py" --pretty
```

Check the active semantic route:

```bash
sergeant llm-status --pretty
```

Require a working route:

```bash
sergeant llm-status --require --pretty
```

### FCC

```bash
export SERGEANT_LLM_PROVIDER=fcc
export SERGEANT_LLM_POLICY=preferred
export SERGEANT_LLM_PROTOCOL=responses
export SERGEANT_LLM_BASE_URL=http://127.0.0.1:8082/v1
sergeant llm-status --require --pretty
sergeant pr-review . --pretty
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

The API key is read from the process environment. It is not returned by `llm-status`, stored by the Command Center, written into reports, or committed to the repository.

### Additional commands

```bash
sergeant app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
sergeant v2-mission . --mission-type pull_request_review --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
sergeant proof-suite . --pretty
sergeant final-proof . --pretty
sergeant verify-standard . --pretty
sergeant battle-tests . --pretty
sergeant ide-bench-contract --pretty
```

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

## Battle testing

Current fixtures include:

- `psf/requests#7502` — focused regression and test-clarity case.
- `pallets/flask#5812` — architecture and lifecycle case.
- `django/django#19610` — URL query-string merge case.

Battle comparison reviews patch text in a temporary workspace. It does not execute target code. Its agreement score remains transparent rather than being treated as an LLM-judged truth score.

## Safety boundary

Sergeant refuses to:

- Execute untrusted pull-request-controlled code.
- Run shell commands supplied by PR content.
- Automatically modify project code.
- Write or merge patches as part of review.
- Use privileged write tokens during analysis.
- Silently fake success after a failed live fetch.
- Treat an LLM or external reviewer as final authority.
- Auto-discover remote model endpoints.
- Emit the semantic-review API key in status or reports.

## Strictest defensible review gate

For high-risk releases:

```bash
export SERGEANT_LLM_POLICY=required
export SERGEANT_LLM_COUNCIL=adaptive
sergeant pr-review . --pretty
```

Then require:

- repository review;
- diff review;
- standard verification;
- capability review;
- semantic route available;
- grounded semantic pass;
- challenger when risk triggers it;
- tests and runtime proof;
- consensus with no unanswered major or blocker.

That is a complete configured gate—not a promise of literal 100% defect detection.

## Public boundary

This repository contains reusable review infrastructure. Private project rules, customer evidence, deployment secrets and write-token operations do not belong in the public repository.

## Contributing

Contributions, issue reports, feature requests and engineering discussions are welcome. Sergeant values evidence-based changes, reproducible results, clear reasoning, respect for existing architecture, standards compliance and useful signals over noisy output.

## Identity

Sergeant / SRG is created by **THETECHGUY DIGITAL SOLUTIONS**.

> Observe. Analyze. Verify.
