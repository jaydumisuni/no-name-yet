# Sergeant Submission Readiness Gate

This is the final gate for using Sergeant in the hackathon submission package.

## Status

```text
Implementation sprint: complete
Submission support: ready
Claim-to-code review: corrected
Release proof: passing
Production hardening: complete
Final live GitHub API proof: captured and enforced
```

## Done

- [x] Live GitHub read-only fetch
- [x] CLI integration
- [x] App Bridge integration
- [x] IDE Bench contract
- [x] Mocked and adversarial tests
- [x] CI proof
- [x] Clean-clone proof
- [x] Battle-test framework
- [x] Requests benchmark
- [x] Flask architecture benchmark
- [x] Battle-test validator
- [x] Cpl council and verified experience
- [x] Production safety boundary
- [x] Real read-only GitHub API ingestion proof
- [x] Sanitized body-free proof artifact
- [x] Release proof through PR with CI and Main Review green

## Honest claim state

### Proven

- Core repo/diff review
- CLI path
- App Bridge path
- IDE Bench contract
- Battle-test framework
- Benchmark cases and validator path
- CI and clean-clone proof
- Secret detection with planted temporary-file positive case
- GitHub-shaped PR comment fixture ingestion
- Full live GitHub API ingestion against the pull request that triggers the proof workflow
- GET-only request evidence
- Repository and PR identity verification
- Read-only workflow permissions
- Sanitized proof artifact with counts and SHA-256 body hashes but no comment bodies

### Implemented / supported

- Live GitHub read-only fetch
- GitHub PR comment payload ingestion
- Evidence-based verdict model
- PASS / NEEDS WORK / BLOCK review outcomes
- Public/private boundary enforcement
- Bounded sandbox and mission permissions

## Final safe submission wording

```text
Sergeant is an evidence-based engineering reviewer with CLI review, App Bridge handoff, IDE Bench contracts, battle-test benchmarks, Cpl council reasoning, CI proof, clean-clone proof, production hardening, and release proof. It verifies claims against implementation and produces PASS / NEEDS WORK / BLOCK verdicts. Secret detection is proven with a planted temporary-file test case. GitHub PR ingestion is proven through both GitHub-shaped fixtures and a real read-only API workflow that captures sanitized request evidence without exposing comment bodies or credentials.
```

## Freeze rule

Do not claim write-side GitHub App delivery, automatic patching, or execution of pull-request-controlled code; those capabilities are neither part of Sergeant's authority nor proven here.

Do not weaken the secret-detection or live-ingestion claims; both are backed by explicit proof artifacts and regression tests.

## Hackathon use

Use Sergeant as a supporting trust layer for the hackathon submission:

- it improves the credibility of Hunter Foreman
- it demonstrates proof-before-claim engineering
- it shows the ecosystem has independent review capability
- it gives judges a reason to trust the submitted code and claims
