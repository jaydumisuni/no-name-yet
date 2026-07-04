# Roadmap

## Phase 0 — Research foundation

Status: started.

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

Goal: run locally against a repository or diff and produce a verdict.

Target command shape:

```bash
main-review scan
main-review review --base main --head feature-branch
main-review report
```

Capabilities:

- repo scanner
- diff parser
- changed file classifier
- secret/public-safety checker
- docs/test gap detector
- simple architecture rule checker
- verdict report

No automatic editing.

## Phase 2 — GitHub PR reviewer

Goal: run on GitHub pull requests safely.

Capabilities:

- read-only PR collector
- limited comment poster
- report artifact
- no analysis write token
- no untrusted code execution
- base-branch policy only

## Phase 3 — Evidence providers

Add optional evidence providers:

- Semgrep
- CodeQL/SARIF importer
- reviewdog-style diagnostics importer
- dependency scanner
- test result importer

All providers must be sandbox-aware.

## Phase 4 — Project memory

Add review memory:

- repeated issue patterns
- project-specific rules
- previous owner decisions
- architecture lessons
- known safe/unsafe paths

This is where it becomes stronger than generic reviewers.

## Phase 5 — Code Ops connection

Connect reviewer verdicts to Code Ops.

Flow:

```text
Reviewer says NEEDS WORK
        ↓
Code Ops plans fixes
        ↓
Code Ops patches
        ↓
Reviewer checks again
```

The reviewer still does not edit by itself.

## Phase 6 — Product identity lock

Once behavior is proven, choose final name.

Criteria:

- memorable
- role-based
- fits THETECHGUY/Hunter ecosystem
- not generic
- easy to say in developer workflow

## Phase 7 — Production hardening

Add:

- sandbox enforcement
- permission tests
- token-scope tests
- policy-change tests
- PR spoofing tests
- malicious config tests
- public/private leak tests

## Phase 8 — Standalone product path

Long-term possibility:

- GitHub App
- local CLI
- cloud dashboard
- self-hosted mode
- organization rules
- enterprise/team review memory

## Current next step

Finish R&D docs, then create first small local prototype that only reads and reports.