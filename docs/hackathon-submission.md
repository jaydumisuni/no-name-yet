# Sergeant Hackathon Submission Brief

## Project

**Sergeant** — an evidence-based engineering reviewer for repositories, pull requests, and AI-assisted development workflows.

## One-line pitch

Sergeant is the reviewer that checks whether code, claims, tests, architecture, and proof match before a project is merged or submitted.

## Problem

AI builders can now generate and patch software quickly, but teams still need an independent reviewer that can answer:

- What changed?
- What risk was introduced?
- Do the docs match the implementation?
- Are secrets or private boundaries exposed?
- Did the project actually prove what it claims?
- Should this change pass, need work, or be blocked?

Most coding assistants focus on writing code. Sergeant focuses on reviewing it.

## Solution

Sergeant analyzes a repository, diff, validated pull-request evidence, App Bridge event, or IDE handoff contract and produces a clear review verdict:

```text
PASS
NEEDS WORK
BLOCK
```

The verdict is supported by evidence, affected files, risk level, confidence, and next steps.

Sergeant deliberately avoids being a blind patch writer. It is built around a safety principle:

```text
Understand danger, but do not execute danger.
```

## Completed proof

The current build includes:

- [x] Production-hardened GitHub read-only fetch
- [x] CLI integration
- [x] App Bridge integration
- [x] IDE Bench contract for VS Code, JetBrains, and AI handoff
- [x] Mocked and adversarial tests
- [x] CI proof
- [x] Clean-clone proof
- [x] Battle-test framework
- [x] Requests-style benchmark
- [x] Flask architecture benchmark
- [x] Battle-test validator
- [x] Cpl multi-model council and verified experience
- [x] Production sandbox and permission boundary
- [x] Real GitHub API ingestion proof
- [x] Sanitized proof artifact
- [x] Release proof through pull-request checks where CI and Main Review are green

## Capability tiers

| Tier | Capability | Purpose |
| --- | --- | --- |
| Tier 1 | Capability Engine | Baseline repo/diff review, evidence collection, and verdict generation. |
| Tier 2 | Review Intelligence | Better reasoning over architecture, docs, risk, and expected behavior. |
| Tier 3 | Evidence Consensus | Combine multiple evidence sources before making a decision. |
| Tier 4 | Verified Learning Loop | Learn from accepted corrections and owner-approved review lessons. |
| Tier 5 | Graduation Benchmark | Use benchmarks to decide when Sergeant is ready for harder review work. |
| Tier 6 | Squad Intelligence | Coordinate permanent officers and Cpl support without losing one final verdict. |
| Phase 7 | Production Hardening | Enforce sandbox, permission, token, identity, pagination, and leak boundaries. |

## What is genuinely proven

- Sergeant can review repositories and diffs.
- Sergeant can run through the CLI.
- Sergeant can receive App Bridge review events.
- Sergeant has a documented IDE Bench contract for IDE and AI handoff workflows.
- Sergeant has mocked, adversarial, CI, and clean-clone proof.
- Sergeant has battle-test benchmark structure and validator logic.
- Secret detection is proven using a planted temporary-file positive case.
- GitHub PR comment payload ingestion is verified using GitHub-shaped fixtures.
- Full live GitHub API ingestion is verified against the real pull request that triggers the proof workflow.
- The live proof uses GET-only requests and read-only workflow permissions.
- The uploaded proof contains request evidence, counts, hashes, and identity metadata but no comment bodies or credentials.

## Accurate live-ingestion wording

```text
Sergeant performs production-hardened live GitHub read-only ingestion. It validates the requested repository and PR, refuses unsafe hosts, redirects, pagination, private evidence, and write-capable classic scopes, and produces a body-free proof artifact. Secret detection is proven with a planted temporary-file positive case.
```

Do not say that Sergeant writes GitHub reviews, applies patches, or executes pull-request-controlled code. Those actions remain outside its authority.

## Why it matters for the hackathon

Sergeant strengthens the full submission because it is not only an AI tool; it is proof infrastructure around AI-built systems.

It shows that the project can:

- move fast without pretending unproven claims are proven
- review AI-generated code before trusting it
- distinguish implemented, tested, inferred, and pending work
- enforce public/private, credential, token, and sandbox boundaries
- support a finish-then-prove engineering workflow
- use one AI-assisted system to review evidence produced by another

## Demo story

```text
Repository or pull request
        ↓
Sergeant validates the boundary and collects evidence
        ↓
Cpl and permanent officers check code, tests, security, architecture, and prior experience
        ↓
Sergeant decides PASS / NEEDS WORK / BLOCK
        ↓
The builder fixes only what evidence supports
        ↓
Clean proof and release proof confirm the work
```

## Submission position

Sergeant should be presented as a working reviewer/proof system that complements Hunter Foreman:

- Hunter Foreman coordinates business operations work.
- Sergeant verifies engineering work before trust, merge, or submission.

Together they show an AI infrastructure pattern where AI systems do work and another AI-assisted system reviews the evidence before the work is accepted.
