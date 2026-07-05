# Sergeant Submission Readiness Gate

This is the final gate for using Sergeant in the hackathon submission package.

## Status

```text
Implementation sprint: complete
Submission support: ready
Claim-to-code review: corrected
Release proof: passing
Final live GitHub API proof: optional unless claimed
```

## Done

- [x] Live GitHub read-only fetch
- [x] CLI integration
- [x] App Bridge integration
- [x] IDE Bench contract
- [x] Mocked tests
- [x] CI proof
- [x] Clean-clone proof
- [x] Battle-test framework
- [x] Requests benchmark
- [x] Flask architecture benchmark
- [x] Battle-test validator
- [x] Release proof through PR with CI and Main Review green
- [x] Honest wording correction for GitHub PR ingestion proof

## Honest claim state

### Proven

- Core repo/diff review
- CLI path
- App Bridge path
- IDE Bench contract
- Battle-test framework
- Two benchmark cases
- Validator path
- CI and clean-clone proof
- Secret detection with planted temp-file positive case

### Implemented / supported

- Live GitHub read-only fetch
- GitHub PR comment payload ingestion
- Evidence-based verdict model
- PASS / NEEDS WORK / BLOCK review outcomes

### Still needs explicit evidence before strongest claim

- Full live GitHub API ingestion against a real PR response

## Final safe submission wording

```text
Sergeant is an evidence-based engineering reviewer with CLI review, app bridge handoff, IDE Bench contracts, battle-test benchmarks, CI proof, clean-clone proof, and release proof. It verifies claims against implementation and produces PASS / NEEDS WORK / BLOCK verdicts. Secret detection is proven with a planted temporary-file test case. GitHub PR comment payload ingestion is verified through GitHub-shaped fixtures, with full live GitHub API ingestion as the next proof step when token/network evidence is captured.
```

## Freeze rule

Do not strengthen the GitHub live-ingestion claim unless a real API call is captured and saved.

Do not weaken the secret-detection claim; it is already proven with a real temp-file positive case.

## Hackathon use

Use Sergeant as a supporting trust layer for the hackathon submission:

- it improves the credibility of Hunter Foreman
- it demonstrates proof-before-claim engineering
- it shows the ecosystem has independent review capability
- it gives judges a reason to trust the submitted code and claims
