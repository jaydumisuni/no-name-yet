# Sergeant Submission Proof

This file is the submission proof checklist for Sergeant.

## Current status

```text
Status: submission-support ready
Code proof: complete for current scope
Release proof: complete through PR checks
Production hardening: complete
Live GitHub API ingestion evidence: captured and artifact-backed
```

## Sprint checklist

- [x] Live GitHub read-only fetch
- [x] CLI integration
- [x] App Bridge integration
- [x] IDE Bench contract for VS Code, JetBrains, and AI handoff
- [x] Mocked and adversarial tests
- [x] CI proof
- [x] Clean-clone proof
- [x] Battle-test framework
- [x] First benchmark: Requests
- [x] Second benchmark: Flask architecture
- [x] Battle-test validator
- [x] Cpl council and verified experience
- [x] Production boundary and sandbox
- [x] Full live GitHub API ingestion proof
- [x] Release proof via pull request where CI and Main Review are green

## Proof categories

### 1. Local reviewer proof

Pass criteria:

- repository review runs from CLI
- diff/PR review produces a verdict
- verdict is one of `PASS`, `NEEDS WORK`, or `BLOCK`
- report includes evidence and reasoning

### 2. GitHub read-only proof

Pass criteria:

- GitHub data is fetched without write permissions
- token is supplied through an environment variable
- workflow permissions remain `contents: read`, `issues: read`, and `pull-requests: read`
- untrusted PR code is not executed
- requested PR number and base repository identity are verified
- same-host/same-repository pagination is bounded
- API redirects are refused
- PR comment payload parsing is verified
- shareable proof omits comment bodies and credentials

Current state:

```text
A real GitHub Actions workflow fetches metadata, issue comments, and review comments for the pull request that triggered it. The workflow validates GET-only request evidence, repository identity, pagination, visibility, and proof shape, then uploads a sanitized JSON artifact containing counts and body hashes rather than comment bodies.
```

Workflow:

```text
.github/workflows/live-github-ingestion-proof.yml
```

Artifact:

```text
live-github-ingestion-proof/live-github-proof.json
```

### 3. Secret detection proof

Pass criteria:

- a planted temporary-file positive case is detected
- the finding is blocker/severe enough to stop a risky merge
- the test does not commit a real or token-shaped secret literal

Current state:

```text
Secret detection is genuinely proven with a temporary test file containing a runtime-constructed synthetic secret-shaped value.
```

### 4. App Bridge proof

Pass criteria:

- external systems can hand a review request to Sergeant
- request contract is stable and path-contained
- public permissions cannot grant write, shell, or untrusted-code execution
- output remains a review verdict, not a patch execution request

### 5. IDE Bench proof

Pass criteria:

- contract supports VS Code style handoff
- contract supports JetBrains style handoff
- contract supports AI tool handoff
- the IDE path remains evidence/report oriented

### 6. Battle-test proof

Pass criteria:

- benchmark cases exist
- validator confirms expected risk/verdict behavior
- Requests-style benchmark is covered
- Flask architecture benchmark is covered
- GitHub PR patch filenames are contained in a temporary sandbox

### 7. Production-hardening proof

Pass criteria:

- unknown actions fail closed
- path traversal, absolute paths, NUL input, and symlink escape are refused
- malformed policies and permissions are refused
- unknown or write-capable token scopes are refused when advertised
- arbitrary hosts, ports, paths, redirects, and pagination targets are refused
- private-repository evidence is blocked by default
- no comment bodies or credentials are present in the uploaded proof artifact

## Claim wording rules

Use this wording:

```text
Sergeant supports production-hardened live GitHub read-only fetch, CLI review, App Bridge review handoff, IDE Bench contracts, battle-test benchmarks, Cpl council reasoning, CI proof, clean-clone proof, and release proof. Secret detection is proven with a planted temporary-file positive case. PR comment ingestion is proven against GitHub-shaped fixtures and through a real read-only GitHub API workflow with sanitized request evidence.
```

Do not claim:

```text
Sergeant writes GitHub review comments, applies patches, or safely executes pull-request-controlled code.
```

Those actions remain outside the reviewer boundary.

## Final submission role

Sergeant should be included as a trust/proof layer in the hackathon submission:

```text
Sergeant is the reviewer that verifies claims, code, tests, risk, and proof before accepting a merge or submission.
```

It should support the main submission narrative without stealing the center from Hunter Foreman.
