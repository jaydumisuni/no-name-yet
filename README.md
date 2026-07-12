<p align="center">
  <img src="resources/readme-top-image.png" alt="Sergeant - open-source engineering reviewer" width="960">
</p>

# Sergeant

**Sergeant (SRG)** is an open-source software engineering review system created by **THETECHGUY DIGITAL SOLUTIONS**.

Sergeant helps developers inspect repositories, review pull requests, verify engineering standards, and produce evidence-based reports. It fits existing developer workflows and provider choices instead of locking a project into one model or platform.

Sergeant is not another one-shot coding assistant. It is a reviewer: it checks work, challenges assumptions, collects proof, and reports what should happen before code is merged or released.

```text
PASS
NEEDS WORK
BLOCK
```

## Who Sergeant is for

- Individual developers who want a second engineering review before shipping.
- Open-source maintainers reviewing pull requests and project changes.
- Software teams that care about standards, evidence, and repeatable review flow.
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

Sergeant can work beside Claude, Codex, Copilot, Cursor, Gemini, local LLMs, or OpenAI-compatible providers. Those tools may help write code. Sergeant stays focused on independent review and evidence.

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

The first step matters: Sergeant should understand the objective, architecture, and intended standard before deciding whether something is wrong.

## Sergeant V2 Command Center

The complete Command Center is the operating interface for the 0.3 release line.

```text
Commander
    ↓
Mission
    ↓
Officers
    ↓
Weapon Manifest
    ↓
Evidence
    ↓
Verification
    ↓
Commander Verdict
    ↓
Audit Trail
```

The VS Code extension provides a compact activity-bar launcher and a full editor Command Center. The JetBrains preview uses the same Command Center through JCEF and falls back to a native Swing panel when JCEF is unavailable.

The interface includes:

- Commander dashboard and live workspace state.
- Mission Planner with repository, changed-file, release, battle, final-proof, IDE, and custom missions.
- Mission briefing, priority, permission, loadout, provider, officer, and weapon controls.
- Live mission progress and runtime evidence.
- Evidence views for static, runtime, UI, documentation, battle, and optional external review.
- Evidence Locker with report history, open, copy, export, and refresh actions.
- Officer deployment and armoury views.
- Settings for providers, writer safety, permissions, IDE awareness, GitHub, battle testing, debug, and advanced controls.
- Review Doctrine, Post-V2 Roadmap, and Guide pages.

### Writer safety boundary

Writer mode is deliberately constrained:

- Disabled by default.
- Draft patches only.
- Human approval required.
- Never auto-merge.

## Review doctrine

```text
Static Evidence
      ↓
Runtime Evidence
      ↓
UI Evidence
      ↓
Docs Verification
      ↓
Cross Verification
      ↓
Confidence
      ↓
Commander Verdict
```

Sergeant does not copy another reviewer's conclusion. It gathers comparable evidence, investigates disagreements, and lets the Commander reason from the evidence.

## Operational status

```text
Status:             Standing By
Release line:       0.3
Current version:    0.3.2
Command Center:     Complete
VS Code:            Supported
Open VSX:           Supported
PyPI:               Supported
JetBrains:          0.3.2-preview
Proof status:       Verified
Battle status:      Passed
```

## Current capability set

### Repository and engineering review

- Repository inspection and understanding.
- Pull-request and change-set review.
- Current-file and changed-file review.
- Architecture and regression-risk checks.
- Static analysis signals.
- Security and safety-boundary checks.
- Documentation drift checks.
- Evidence consensus and standards verification.
- Verified learning and squad-style review intelligence.

### Developer workflow

- CLI review flow.
- App bridge contract.
- IDE Bench contract for VS Code, PyCharm, JetBrains, and AI handoff.
- Full VS Code Command Center.
- JetBrains Command Center preview.
- Read-only GitHub PR comment ingestion.
- Live GitHub review bridge.
- Local, self-hosted, and OpenAI-compatible provider choices.

### Proof and battle validation

- Battle-test fixtures and validator.
- Static review-signal comparison.
- Live PR patch fetch for battle comparison.
- Battle comparison harness against Sergeant output.
- CI and clean-clone proof.
- App bridge and IDE contract proof.
- Browser-rendered Command Center proof at desktop and compact IDE widths.
- PyPI wheel/source validation, VSIX packaging, and JetBrains plugin packaging.

## Installation

### Python / CLI

Install from PyPI:

```bash
python -m pip install sergeant-reviewer==0.3.2
```

Or install from source:

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
code --install-extension sergeant-reviewer-0.3.2.vsix --force
```

After installation, open **Sergeant** from the activity bar. Use **Open Full Command Center** for the complete V2 interface.

Available commands:

- `Sergeant: Open Full Command Center`
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

### JetBrains IDEs

The `0.3.2-preview` plugin targets the 2025.2 / build 252 line and provides the shared Command Center in supported IntelliJ-platform IDEs, including IntelliJ IDEA, PyCharm, WebStorm, Android Studio, Rider, CLion, DataGrip, GoLand, PhpStorm, RustRover, RubyMine, and related products.

The JetBrains plugin invokes the installed Sergeant CLI. Install the CLI first:

```bash
python -m pip install sergeant-reviewer==0.3.2
```

When necessary, set `SERGEANT_CLI` to the executable path.

## Quick start

Review the current repository:

```bash
sergeant review . --pretty
```

`main-review` remains a backwards-compatible CLI alias.

Run an app bridge review:

```bash
sergeant app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Build a V2 mission packet:

```bash
sergeant v2-mission . --mission-type pull_request_review --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Run the proof suite and final proof:

```bash
sergeant proof-suite . --pretty
sergeant final-proof . --pretty
```

Verify the standard:

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

Fetch read-only live GitHub PR comments:

```bash
sergeant live-github-comments owner/repo 12 --pretty
```

Run live GitHub comments through the review bridge:

```bash
sergeant live-github-review owner/repo 12 . --pretty
```

Show the IDE handoff contract:

```bash
sergeant ide-bench-contract --pretty
```

Validate battle fixtures:

```bash
sergeant battle-tests --pretty
```

Run a live battle comparison:

```bash
sergeant battle-compare battle-tests/psf-requests-7502.json --token YOUR_READ_ONLY_GITHUB_TOKEN --pretty
```

`battle-compare` fetches real PR patch metadata, writes patch text into a temporary review workspace, runs Sergeant against it, and compares the output against expected findings. It is read-only and does not execute target-repository code.

## Battle testing

Current fixtures include:

- `psf/requests#7502` — focused regression and test-clarity case.
- `pallets/flask#5812` — larger architecture and lifecycle case.
- `django/django#19610` — URL query-string merge case.

Battle proof has three layers:

1. **Static fixture proof** — committed fixtures, review signals, expected findings, and coverage.
2. **Battle-aware evidence rules** — deterministic rules learned from committed fixture patterns.
3. **Live battle comparison** — real PR patch metadata compared with Sergeant findings.

```text
GitHub Battle Tests:      Passed
Repository Battles:       Passed
Pull Request Battles:     Passed
Review Comparison:        Passed
Evidence Validation:      Passed
Third Fixture:            Passed
```

Live battle comparison reviews patch text in a temporary workspace. It does not execute target code, and its agreement score remains a transparent keyword-overlap comparison rather than an LLM-judged semantic benchmark.

## Proof suite

```text
CI Proof:                    Passed
Clean Clone Proof:           Passed
App Bridge Proof:            Passed
IDE Contract Proof:          Passed
Mocked GitHub Proof:         Passed
Battle Proof:                Passed
Command Center Browser Proof: Passed
VSIX Packaging:              Passed
Python Distribution Proof:   Passed
JetBrains Packaging:         Passed
Release Proof:               Passed
```

## Public boundary

This repository contains reusable review infrastructure:

- Review engine and static analysis.
- Battle-aware evidence rules for committed fixtures.
- Evidence consensus and verified learning framework.
- Squad-style review intelligence.
- App and IDE contracts.
- Read-only GitHub ingestion.
- Live PR diff fetch for battle comparison.
- Battle-test validation.
- VS Code and JetBrains Command Center integrations.

Private project rules, customer evidence, deployment secrets, and write-token operations do not belong in the public repository.

## Safety boundary

Sergeant refuses to:

- Execute untrusted pull-request-controlled code.
- Run shell commands supplied by PR content.
- Automatically modify project code.
- Write or merge patches as part of review.
- Use privileged write tokens during analysis.
- Silently fake success after a failed live fetch.
- Treat external reviewers as final authority.

## Sergeant terminology

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

The terminology is intended to make Sergeant disciplined, organized, accountable, and clear—not to turn engineering review into a game.

## Post-V2 roadmap

The completed V2 core remains focused on:

```text
Commander → Mission → Officers → Weapon Manifest → Evidence → Verdict → Audit Trail
```

Later work is deliberately separated:

- Mission templates and live monitoring.
- Review replay and collaboration.
- Multi-repository operations.
- Shared knowledge-base integration.
- Analytics and recurring-issue trends.
- Plugin / Weapon SDK.
- Wider language and ecosystem battle testing.

## Contributing

Contributions, issue reports, feature requests, and engineering discussions are welcome. Sergeant values evidence-based changes, reproducible results, clear reasoning, respect for existing architecture, standards compliance, and useful signals over noisy output.

## Identity

Sergeant / SRG is created by **THETECHGUY DIGITAL SOLUTIONS**.

> Observe. Analyze. Verify.
