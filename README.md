<p align="center">
  <img src="resources/readme-top-image.png" alt="Sergeant - open-source engineering reviewer" width="960">
</p>

# Sergeant

**Sergeant (SRG)** is an open-source software engineering review system created by **THETECHGUY DIGITAL SOLUTIONS**.

Sergeant reviews repositories, changed files, pull-request evidence, engineering standards, proof gates, and release readiness. It is built around one rule:

> **Evidence first. Verdict second. Nothing is assumed.**

Sergeant is not a one-shot code generator. Coding assistants may help write code; Sergeant independently checks the work, records evidence, challenges claims, and returns a review outcome:

```text
PASS
NEEDS WORK
BLOCK
```

## Current release line

| Surface | Version | Status |
| --- | --- | --- |
| VS Code Marketplace / Open VSX | `0.3.2` | Full Command Center |
| PyPI package | `0.3.2` | CLI and review engine |
| JetBrains Marketplace | `0.3.2-preview` | Full Command Center preview |
| GitHub release artifacts | `v0.3.2` | VSIX, Python distributions, JetBrains ZIP |

The earlier `0.3.0` and `0.3.1-preview` artifacts remain immutable. `0.3.2` is the completed patch release in the same **0.3 multiplatform release line**.

## The Command Center

The completed Command Center implements the written Sergeant V2 operating model:

```text
Commander
   ↓
Mission
   ↓
Officers
   ↓
Weapon Manifest / Armoury
   ↓
Evidence
   ↓
Verification
   ↓
Commander Verdict
   ↓
Audit Trail
```

### Included surfaces

- **Commander Dashboard** — current workspace, branch, changed files, mission state, verdict and confidence.
- **Mission Planner** — repository, pull-request, release, battle, final-proof, IDE and custom mission intake.
- **Evidence** — static, runtime, UI, documentation, battle and explicitly enabled external evidence.
- **Evidence Locker** — latest report, mission history, copy, open and export actions.
- **Officers / Armoury** — officer responsibilities, weapon manifest and deployment state.
- **Settings** — general, providers, writer, permissions, IDE, GitHub, battle, debug and advanced groups.
- **Doctrine** — the review sequence and the THETECHGUY engineering standard.
- **Roadmap** — post-V2 work kept separate from the completed V2 interface.
- **Guide** — in-product explanation of missions, officers, armoury, evidence, safety and battle testing.

### Real runtime state

The IDE integrations do not generate fake mission progress, verdicts or report history. They receive state from the host integration and record actual command results.

Runtime-aware fields include:

- workspace and project name;
- Git branch and changed-file count;
- active file where the host exposes it;
- mission type, briefing, priority, selected provider and loadout;
- command status and exit result;
- findings, report time and mission history.

The Command Center escapes runtime-derived text before HTML rendering and constrains IDE webview content with a Content Security Policy.

## VS Code integration

The activity-bar view provides a compact control surface. **Open Full Command Center** launches the complete editor-sized interface.

Commands:

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

Build and install locally:

```bash
npx @vscode/vsce package --no-dependencies --out sergeant-reviewer-0.3.2.vsix
code --install-extension sergeant-reviewer-0.3.2.vsix --force
```

## JetBrains integration

The JetBrains preview uses a JCEF Command Center backed by the shared Sergeant CLI. It supports the same mission set and preserves mission context in the Evidence Locker.

Supported platform products are determined by the platform dependency in `plugin.xml`. The current build targets JetBrains build `252+` and therefore supports compatible 2025.2-era IDE builds. A native Swing fallback remains available when JCEF is unavailable.

Build locally:

```bash
gradle -p adapters/jetbrains clean buildPlugin
```

The ZIP is written to:

```text
adapters/jetbrains/build/distributions/
```

## Provider selector boundary

The Command Center can record these provider choices:

- Local Model
- OpenAI-compatible API
- GPT
- Claude
- Gemini
- Copilot / Codex Handoff
- Private/Internal Adapter
- Custom Endpoint

The selected provider is stored as mission and settings context. **Selecting a provider does not invent an integration or send data automatically.** Actual provider execution requires an installed/configured adapter and the required user permission.

## Writer safety boundary

Pass to Writer is intentionally constrained:

- disabled by default;
- draft patches only;
- human approval required;
- never auto-merge.

The public review path remains read-only by default and does not execute untrusted pull-request-controlled code.

## Installation

From PyPI:

```bash
python -m pip install --upgrade sergeant-reviewer==0.3.2
```

From source:

```bash
git clone https://github.com/jaydumisuni/Sergeant.git
cd Sergeant
python -m pip install -e .
```

Requires Python 3.10 or newer.

## Quick start

Review a repository:

```bash
sergeant review . --pretty
```

Review an application/change-set contract:

```bash
sergeant app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Build a V2 mission packet:

```bash
sergeant v2-mission . \
  --mission-type pull_request_review \
  --mode pull_request \
  --files "src/app.py,tests/test_app.py" \
  --pretty
```

Run final proof:

```bash
sergeant final-proof . --pretty
```

Run the end-to-end proof suite:

```bash
sergeant proof-suite . --pretty
```

Verify the THETECHGUY engineering standard:

```bash
sergeant verify-standard . --pretty
```

Show the IDE handoff contract:

```bash
sergeant ide-bench-contract --pretty
```

`main-review` remains available as a backwards-compatible command alias.

## Review doctrine

Sergeant follows this sequence:

```text
Static Evidence
      ↓
Runtime Evidence
      ↓
UI Evidence
      ↓
Documentation Verification
      ↓
Cross Verification
      ↓
Confidence
      ↓
Commander Verdict
```

The implementation follows these engineering principles:

1. **Finish, then prove** — complete the intended implementation, review it, freeze it, then perform clean-clone and runtime proof.
2. **Code should justify execution** — execute code expecting success because the reasoning and review already support it.
3. **Claims must match implementation** — compare documentation, release notes and marketing claims against actual behavior.
4. **Evidence before conclusions** — distinguish proof, inference, uncertainty and unresolved conflict.
5. **Tests are proof, not discovery** — design and review first; use execution to confirm the implementation.

## Battle testing

Sergeant is tested against committed real-world review fixtures as well as synthetic unit cases.

Current fixtures include:

- `psf/requests#7502`
- `pallets/flask#5812`
- `django/django#19610`

Battle proof includes:

1. fixture-contract validation;
2. deterministic battle-aware evidence rules for committed patterns;
3. live read-only PR patch comparison;
4. expected-finding agreement and disagreement reporting;
5. explicit caveats for evidence that could not be verified.

Live battle comparison does not execute target repository code. It reviews fetched patch evidence in a temporary workspace.

## Proof standard

The multiplatform proof workflow verifies:

- Python tests and clean-clone behavior;
- JavaScript syntax;
- Command Center navigation and controls;
- desktop and compact IDE rendering;
- horizontal-overflow and visual-collision checks;
- hostile runtime-state escaping;
- mission briefing/audit payloads;
- Python wheel and source distributions;
- VSIX packaging;
- JetBrains compilation and bundled UI resources;
- coordinated release versions.

The repository also runs independent Main Review and clean-clone CI before merge.

## Public safety boundary

Sergeant refuses to:

- execute untrusted pull-request-controlled code;
- run shell commands extracted from PR content;
- automatically modify project code during review;
- silently publish or merge a generated patch;
- use privileged write tokens for ordinary analysis;
- fake success after a failed live fetch;
- treat an external reviewer as final authority.

Private customer evidence, deployment secrets, project-specific credentials and privileged write operations do not belong in this public repository.

## Repository structure

```text
main_review/                     Python review engine and CLI
src/vscode/                      VS Code host integration
resources/sergeant-command-*     Shared Command Center UI
adapters/jetbrains/              JetBrains host integration
tests/                           Unit, contract and browser proof
battle-tests/                    Committed battle fixtures
docs/                            Architecture, standards and roadmap
.github/workflows/               CI, proof and publishing workflows
```

## Post-V2 roadmap

The completed V2 interface is intentionally separated from later expansion work:

- live multi-repository operations;
- reusable mission templates;
- collaborative review and replay;
- knowledge-base integration;
- trend and recurring-issue analytics;
- plugin / Weapon SDK;
- wider language and framework battle coverage.

## Contributing

Contributions should be evidence-based, reproducible and consistent with the existing architecture. Useful areas include battle fixtures, false-positive/false-negative comparisons, language knowledge packs, IDE integration feedback and documentation improvements.

## Identity

Sergeant / SRG is created by **THETECHGUY DIGITAL SOLUTIONS**.

> **Observe. Analyze. Verify.**
