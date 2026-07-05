# Roadmap

## Current status

Sergeant has moved past the original R&D-only state into a working reviewer/proof system.

Completed submission sprint:

- Live GitHub read-only fetch
- CLI integration
- App Bridge integration
- IDE Bench contract for VS Code, JetBrains, and AI handoff
- Mocked tests
- CI proof
- Clean-clone proof
- Battle-test framework
- Requests benchmark
- Flask architecture benchmark
- Battle-test validator
- Release proof through PR where CI and Main Review are green

Important claim correction:

```text
Secret detection is genuinely proven with a planted temp-file positive case.
GitHub PR comment payload ingestion is verified with GitHub-shaped fixtures.
Full live GitHub API ingestion remains the next proof step before making the strongest live-ingestion claim.
```

## Phase 0 — Research foundation

Status: complete.

Goals:

- Capture CodeRabbit/PwnedRabbit lessons.
- Study Qodo / PR-Agent patterns.
- Study static-analysis review tools.
- Define trust boundaries.
- Define verdict model.
- Keep identity open until role is fully clear.

Outputs:

- product brief
- source list
- comparison matrix
- architecture draft
- security model
- verdict model
- identity notes

## Phase 1 — Minimal local reviewer

Status: complete for current submission scope.

Goal: run locally against a repository or diff and produce a verdict.

Command shape:

```bash
main-review review . --pretty
main-review app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Capabilities:

- repo scanner
- diff parser
- changed file classifier
- secret/public-safety checker
- docs/test gap detector
- architecture rule checker
- verdict report

No automatic editing.

## Phase 2 — GitHub PR reviewer

Status: partial / proof-gated.

Goal: run on GitHub pull requests safely.

Capabilities:

- read-only PR collector
- live GitHub read-only fetch support
- PR comment payload ingestion
- no analysis write token
- no untrusted code execution
- base-branch policy only

Proof boundary:

```text
GitHub-shaped payload ingestion is verified.
Full live API ingestion requires captured token/network evidence before being claimed as fully proven.
```

## Phase 3 — Evidence providers

Status: started through evidence consensus and battle-test validator.

Evidence direction:

- secret detection
- architecture findings
- docs-vs-implementation findings
- test/CI evidence
- benchmark evidence

Future optional providers:

- Semgrep
- CodeQL/SARIF importer
- reviewdog-style diagnostics importer
- dependency scanner
- test result importer

All providers must be sandbox-aware.

## Phase 4 — Project memory / verified learning

Status: implemented for current verified-learning path.

Review memory direction:

- repeated issue patterns
- project-specific rules
- previous owner decisions
- architecture lessons
- known safe/unsafe paths
- accepted corrections

This is where Sergeant becomes stronger than generic reviewers.

## Phase 5 — Code Ops / App Bridge connection

Status: implemented for current app bridge scope.

Flow:

```text
Reviewer says NEEDS WORK
        ↓
Builder or Code Ops plans fixes
        ↓
Builder patches
        ↓
Sergeant checks again
```

The reviewer still does not edit by itself.

## Phase 6 — Product identity lock

Status: complete.

Final working identity: **Sergeant**.

Reason:

- memorable
- role-based
- fits THETECHGUY/Hunter ecosystem
- distinct from Hunter Foreman
- easy to say in developer workflow

## Phase 7 — Production hardening

Status: next major phase.

Add:

- sandbox enforcement
- permission tests
- token-scope tests
- policy-change tests
- PR spoofing tests
- malicious config tests
- public/private leak tests
- full live GitHub API ingestion proof

## Phase 8 — Standalone product path

Long-term possibility:

- GitHub App
- local CLI
- cloud dashboard
- self-hosted mode
- organization rules
- enterprise/team review memory

## Current next step

For hackathon use, Sergeant is ready as a supporting trust/proof layer.

Next proof step if needed:

```text
Capture a full live GitHub API ingestion run against a real PR response and save the evidence before claiming full live PR ingestion.
```
