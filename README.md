<p align="center">
  <img src="resources/readme-top-image.png" alt="Sergeant - open-source engineering reviewer" width="960">
</p>

# Sergeant

**Sergeant (SRG)** is an open-source software engineering review system created by **THETECHGUY DIGITAL SOLUTIONS**.

Sergeant helps developers inspect repositories, review pull requests, verify engineering standards, and produce evidence-based reports. It is built to fit existing developer workflows and AI provider choices instead of locking a project into one model or platform.

Sergeant is not another one-shot coding assistant. It is a reviewer: it checks work, challenges assumptions, collects proof, and reports what should happen before code is merged or released.

```text
PASS
NEEDS WORK
BLOCK
```

## Who Sergeant is for

Sergeant is useful for:

- Individual developers who want a second engineering review before shipping.
- Open-source maintainers reviewing pull requests and project changes.
- Software teams that care about standards, evidence, and repeatable review flow.
- AI-assisted development workflows where generated code still needs independent review.
- Self-hosted or model-agnostic environments that should not depend on one provider.

## Why Sergeant exists

Most AI coding tools focus on generating code.

Sergeant focuses on reviewing software engineering work.

It helps developers and teams answer:

- Is this change safe enough to merge?
- What evidence supports the review?
- What standards does the work meet or miss?
- What must be fixed before release?
- What did external reviewers, CI, tests, or real project evidence show?
- Where is the real engineering risk?

## Core principles

- **Evidence before opinion.**
- **Standards before assumptions.**
- **Review before merge.**
- **Verification before release.**
- **Human judgment remains final.**

Sergeant can work beside coding assistants such as Claude, Codex, Copilot, Cursor, Gemini, local LLMs, or OpenAI-compatible providers. Those tools may help write code. Sergeant stays focused on independent review and evidence.

## Engineering workflow

Sergeant follows a disciplined engineering workflow:

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

The first step matters: Sergeant should understand the objective, architecture, and intended standard before deciding whether something is wrong.

## How Sergeant works

```text
Developer
   │
   ▼
Sergeant
   │
   ├─ Repository
   ├─ Pull Request
   └─ Change Set
   │
   ▼
Evidence Collection
   │
   ▼
Standards Verification
   │
   ▼
Report Ready
```

Sergeant reviews the available evidence, compares it against engineering standards, and returns a clear outcome: `PASS`, `NEEDS WORK`, or `BLOCK`.

## Operational status

```text
Status:        Standing By
Version:       v2 command-system phase
Mission:       Operational
Proof Status:  Verified
Battle Status: Passed
V1 Baseline:   Released and pinned
```

## Current capability set

### Repository review

- Repository inspection
- Pull request and change-set review
- Changed-file and diff analysis
- Repository understanding
- Architecture and regression risk checks

### Engineering review

- Static analysis signals
- Security and safety boundary checks
- Documentation drift checks
- Evidence consensus
- Verified learning loop
- Standards verification
- Review intelligence
- Squad-style review intelligence

### Developer workflow

- CLI review flow
- App bridge contract
- IDE Bench contract for VS Code, PyCharm, JetBrains, and AI handoff
- VS Code extension commands
- Read-only GitHub PR comment ingestion
- Live GitHub review bridge
- Works with local models, self-hosted deployments, and OpenAI-compatible providers

### Proof and battle validation

- Battle-test fixtures and validator
- Static review-signal comparison
- Live PR patch fetch for battle comparison
- Battle comparison harness against Sergeant review output
- Battle-aware evidence rules for committed fixture patterns
- CI proof
- Clean-clone proof
- App bridge proof
- IDE contract proof
- Mocked live GitHub proof
- Release proof checks

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
sergeant review . --pretty
```

`main-review` is also kept as a backwards-compatible CLI alias for V1.

Run the app bridge contract:

```bash
sergeant app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Fetch read-only live GitHub PR comments:

```bash
sergeant live-github-comments owner/repo 12 --pretty
```

Run live GitHub comments through the review bridge:

```bash
sergeant live-github-review owner/repo 12 . --pretty
```

Show IDE handoff contract:

```bash
sergeant ide-bench-contract --pretty
```

Build the V2 mission, briefing, loadout, confidence, and audit packet:

```bash
sergeant v2-mission . --mission-type pull_request_review --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Run from PyCharm or VS Code without installing the console script:

```bash
python sergeant.py ide-bench-contract --pretty
```

VS Code launch configs are in `.vscode/launch.json`.

PyCharm run configs are in `.idea/runConfigurations/`.

Install Sergeant as a local VS Code extension:

```bash
npx @vscode/vsce package --no-dependencies
code --install-extension sergeant-reviewer-0.2.2.vsix --force
```

After installation, Sergeant appears in the VS Code activity bar as a Command Center and provides these commands from any workspace:

- `Sergeant: Review Workspace`
- `Sergeant: App Bridge Review`
- `Sergeant: Review Current File`
- `Sergeant: Review Changed Files`
- `Sergeant: Build V2 Mission`
- `Sergeant: Run Proof Suite`
- `Sergeant: Run Final Proof`
- `Sergeant: Verify Standard`
- `Sergeant: Validate Battle Tests`
- `Sergeant: IDE Bench Contract`
- `Sergeant: Open Last Report`
- `Sergeant: Copy Last Report`
- `Sergeant: Export Last Report`

Validate battle-test fixtures and static review-signal comparisons:

```bash
sergeant battle-tests --pretty
```

Run a live battle comparison against one fixture:

```bash
sergeant battle-compare battle-tests/psf-requests-7502.json --token YOUR_READ_ONLY_GITHUB_TOKEN --pretty
```

`battle-compare` fetches the real PR patch list through the GitHub API, writes the patch text into a temporary review workspace, runs Sergeant against it, and compares Sergeant's output against the fixture's expected findings using transparent keyword-overlap scoring. It does not execute target repository code.

Run the self-check gate:

```bash
sergeant verify-standard --pretty
```

A clean self-check returns:

```json
{
  "status": "verified",
  "next_actions": []
}
```

## Battle testing

Sergeant is not tested only against synthetic examples.

Battle testing means running Sergeant against real public pull requests and real engineering review situations, then comparing its findings with the kinds of concerns maintainers and reviewers actually raised.

Current fixtures include:

- `psf/requests#7502` — focused regression and test-clarity review case
- `pallets/flask#5812` — larger architecture and lifecycle review case
- `django/django#19610` — third URL query-string merge review case

Battle proof has three layers:

1. **Static fixture proof** — verifies committed battle fixtures, review signals, expected findings, and static comparison coverage.
2. **Battle-aware evidence rules** — deterministic static rules learned from committed fixture patterns and extended through the Django query-string case so V1 can recognize those review signals in patch text.
3. **Live battle comparison** — fetches real PR patch metadata, runs Sergeant against reviewable patch content, then reports matched expected findings, missed expected findings, false-positive candidates, agreement rate, and caveats.

Current battle status:

```text
GitHub Battle Tests:      Passed
Repository Battles:       Passed
Pull Request Battles:     Passed
Review Comparison:        Passed
Evidence Validation:      Passed
Third Fixture:            Passed
```

Important scope note: live battle comparison reviews GitHub PR patch text in a temporary workspace. It is read-only and does not execute target repository code. It is not a full historical checkout of the PR base/head repository state, and the agreement score is keyword-overlap based with documented synonym expansion rather than semantic or LLM-judged. V1 battle-aware evidence rules are deterministic static rules for committed fixture patterns, not a broad semantic reviewer or a held-out generalization benchmark.

The next proof phase is wider language and ecosystem battle testing across Python, JavaScript / TypeScript, Go, Rust, Java / Kotlin, C#, and C / C++ repositories.

## Proof suite

Sergeant treats proof as more than ordinary unit tests.

The proof suite is intended to show that the project can be installed, executed, reviewed, packaged, and validated in a repeatable way.

Current v1 proof status:

```text
CI Proof:                 Passed
Clean Clone Proof:        Passed
App Bridge Proof:         Passed
IDE Contract Proof:       Passed
Mocked GitHub Proof:      Passed
Battle Proof:             Passed
Release Proof:            Passed
```

## Public boundary

This public repository contains reusable review infrastructure.

Public:

- review engine
- static analysis
- battle-aware evidence rules for committed fixture patterns
- evidence consensus
- verified learning framework
- squad-style review intelligence
- app and IDE contracts
- read-only GitHub ingestion
- live PR diff fetch for battle comparison
- battle-test validation

Private/project-specific rules, customer evidence, deployment secrets, and write-token operations do not belong in the public repository.

## Safety boundary

Sergeant is a reviewer, not an unsafe execution engine.

It refuses to:

- Execute untrusted pull-request-controlled code
- Run shell commands from PR content
- Automatically modify project code
- Write patches as part of review
- Use privileged write tokens during analysis
- Silently fake success after a failed live fetch
- Treat external reviewers as final authority

## Sergeant terminology

Sergeant uses a small amount of military-inspired language to make reviews structured and memorable without making the tool hard to understand. Every term has a plain-language meaning.

| Sergeant term | Meaning |
| --- | --- |
| Standing By | Ready for the next review |
| Orders Received | Review request accepted |
| Deploy Review Squad | Start the review process |
| Evidence Collected | Findings and proof gathered |
| Report Ready | Review completed |
| Attention Required | Action is recommended |
| Evidence Locker | Saved reports or review history |
| After Action Report | Detailed review report |
| Verified | Confirmed by evidence |
| Unable to Verify | More evidence is needed |

The goal is not to turn the interface into a military game. The goal is to make Sergeant feel disciplined, organized, accountable, and clear.

## Roadmap

### V1

- Open-source reviewer foundation
- CLI review flow
- GitHub integration
- VS Code extension foundation
- App and IDE contracts
- Proof suite
- Battle testing
- Battle-aware evidence rules for committed fixture patterns
- Public safety boundaries

### V2

- V2 command-system layer implemented
- Mission intake, briefing, and loadout packets
- Shared armoury and weapon manifests
- Officer blueprints and adaptive deployment
- Adaptive confidence and audit trail
- Command Center UI polish
- Better Review Squad workflow
- Evidence Locker / report history
- Faster review pipeline
- Better battle visualization
- More language and framework coverage
- Improved report experience
- Self-hosted and OpenAI-compatible provider options

## Contributing

Contributions, issue reports, feature requests, and engineering discussions are welcome.

Sergeant values:

- evidence-based changes
- reproducible results
- clear reasoning
- respect for existing architecture
- standards compliance
- useful review signals over noisy AI output

Useful areas for community help:

- battle-test fixtures from real public pull requests
- language/framework knowledge packs
- false-positive and false-negative comparisons
- IDE integration feedback
- documentation improvements

## Identity

Sergeant / SRG is created by **THETECHGUY DIGITAL SOLUTIONS**.

> Observe. Analyze. Verify.
