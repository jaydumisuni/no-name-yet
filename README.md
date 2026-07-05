<p align="center">
  <img src="resources/readme%20top%20imsge.png" alt="Sergeant - open-source engineering reviewer" width="860">
</p>

# Sergeant

**Sergeant (SGT.)** is an open-source engineering reviewer created by **THETECHGUYDS**.

Sergeant reviews repositories, pull requests, and change sets before code is merged. It does not write patches by itself. It inspects evidence, compares the work against standards, and returns a clear review outcome.

```text
PASS
NEEDS WORK
BLOCK
```

## What Sergeant does

- Reviews repositories and pull requests
- Inspects changed files and diffs
- Detects risk in architecture, security, tests, regressions, and documentation drift
- Ingests read-only GitHub PR comments
- Compares external review evidence without treating other reviewers as final authority
- Produces structured CLI, app bridge, and IDE handoff output
- Validates battle-test fixtures from real public pull requests
- Keeps review safety boundaries explicit

## Why Sergeant exists

Most AI coding tools focus on writing code.

Sergeant focuses on reviewing it.

It is designed to help developers and teams answer:

- Is this change safe enough to merge?
- What evidence supports the review?
- What must be fixed before release?
- What did external reviewers or humans notice?
- Where is the real risk?

## Core principle

> Evidence before opinion. Specialists advise. Sergeant commands.

Sergeant can work beside coding assistants such as Claude, Codex, Copilot, Cursor, Gemini, and local LLMs. Those tools may help write code. Sergeant stays focused on independent review.

## Safety boundary

Sergeant is a reviewer, not an unsafe execution engine.

It refuses to:

- Execute untrusted pull-request-controlled code
- Run shell commands from PR content
- Automatically modify project code
- Write patches as part of review
- Use privileged write tokens during analysis
- Silently fake success after a failed live fetch
- Treat external reviewers as authorities

## Current v1 capability set

- Capability engine
- Review intelligence
- Evidence consensus
- Verified learning loop
- Graduation benchmark
- Squad intelligence
- App bridge contract
- IDE Bench contract for VS Code, PyCharm, JetBrains, and AI handoff
- Read-only live GitHub PR comment fetch
- Live GitHub review bridge
- Boundary and visibility policy checks
- Battle-test fixtures and validator
- CI and clean-clone proof

## Installation

```bash
git clone https://github.com/jaydumisuni/Sergeant.git
cd Sergeant
python -m pip install -e .
```

Requires Python 3.10 or newer.

## Quick start

Review the current repository:

```bash
main-review review . --pretty
```

Run the app bridge contract:

```bash
main-review app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Fetch read-only live GitHub PR comments:

```bash
main-review live-github-comments owner/repo 12 --pretty
```

Run live GitHub comments through the review bridge:

```bash
main-review live-github-review owner/repo 12 . --pretty
```

Show IDE handoff contract:

```bash
main-review ide-bench-contract --pretty
```

Run from PyCharm or VS Code without installing the console script:

```bash
python sergeant.py ide-bench-contract --pretty
```

VS Code launch configs are in `.vscode/launch.json`.

PyCharm run configs are in `.idea/runConfigurations/`.

Validate battle-test fixtures:

```bash
main-review battle-tests --pretty
```

Run the self-check gate:

```bash
main-review verify-standard --pretty
```

A clean self-check returns:

```json
{
  "status": "verified",
  "next_actions": []
}
```

## Battle testing

Sergeant includes battle-test fixtures from real public pull requests. These fixtures are used to compare Sergeant against real review discussions and expected review signals.

Current fixtures include:

- `psf/requests#7502` — focused regression and test-clarity review case
- `pallets/flask#5812` — larger architecture and lifecycle review case

The next proof phase is wider language and ecosystem battle testing.

## Public boundary

This public repository contains reusable review infrastructure.

Public:

- review engine
- static analysis
- evidence consensus
- verified learning framework
- squad-style review intelligence
- app and IDE contracts
- read-only GitHub ingestion
- battle-test validation

Private/project-specific rules, customer evidence, deployment secrets, and write-token operations do not belong in the public repository.

## Status

**Sergeant v1 foundation is implemented and self-verifying.**

The current v1 foundation has passed CI, clean-clone proof, app bridge proof, IDE contract proof, mocked live GitHub proof, battle-test validation, and release proof checks.

Cross-language ranking proof remains the next improvement phase.

## Proof (Still to do)

- Run against real repositories in multiple languages:
  - Python
  - JavaScript / TypeScript
  - Go
  - Rust
  - Java / Kotlin
  - C#
  - C/C++
- Compare Sergeant's findings with what maintainers actually reviewed.
- Record agreement, misses, and false positives.

Repository: [jaydumisuni/Sergeant](https://github.com/jaydumisuni/Sergeant)

## Contributing

Contributions, issue reports, feature requests, and engineering discussions are welcome.

Useful areas for community help:

- battle-test fixtures from real public pull requests
- language/framework knowledge packs
- false-positive and false-negative comparisons
- IDE integration feedback
- documentation improvements

## Identity

Sergeant / SGT. is created by **THETECHGUYDS**.
