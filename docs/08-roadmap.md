# Roadmap

## Current status

Sergeant has moved past the original R&D-only state into a working, production-hardened reviewer/proof system with a first standalone product surface.

Completed foundation and product work:

- Live GitHub read-only fetch
- CLI integration
- App Bridge integration
- IDE Bench contract for VS Code, JetBrains, and AI handoff
- Mocked and adversarial tests
- CI proof
- Clean-clone proof
- Battle-test framework
- Requests benchmark
- Flask architecture benchmark
- Battle-test validator
- Cpl council command and verified experience
- Production safety boundary
- Full live GitHub API ingestion proof against a real pull request
- Dependency-free standalone HTTP service
- Existing Command Center connected to live self-hosted APIs
- HMAC-verified GitHub webhook intake
- Installed-wheel Command Center packaging
- Hardened non-root container and Compose deployment
- Release proof through PRs where CI and Main Review are green

Current defensible claim:

```text
Secret detection is proven with a planted temporary-file positive case.
GitHub-shaped payload ingestion is verified with fixtures.
Full live GitHub API ingestion is proven by a real read-only workflow that captures request evidence, repository identity, token-scope assessment, counts, and body hashes while omitting comment bodies.
Sergeant can run as an authenticated self-hosted service from source, an installed wheel, or a hardened read-only container while preserving the reviewer/no-write authority boundary.
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

Status: complete.

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

Status: read-only ingestion complete; write-side GitHub App delivery remains a future product path.

Implemented capabilities:

- read-only PR metadata and comment collector
- verified live GitHub API fetch
- PR comment payload ingestion
- repository and PR identity checks
- no analysis write token
- no untrusted code execution
- base-repository policy
- bounded same-host pagination
- sanitized proof artifact

Proof boundary:

```text
GitHub-shaped payload ingestion is verified.
A real GitHub Actions run has captured live metadata, issue-comment, and review-comment requests with read-only permissions and body-free proof output.
```

## Phase 3 — Evidence providers

Status: implemented baseline through evidence consensus and battle-test validator.

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

All providers must remain sandbox-aware.

## Phase 4 — Project memory / verified learning

Status: implemented for canonical lessons plus Cpl/officer/model/weapon experience.

Review memory direction:

- repeated issue patterns
- project-specific rules
- previous owner decisions
- architecture lessons
- known safe/unsafe paths
- accepted corrections
- model and weapon service records

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

Status: complete for the current public reviewer boundary.

Implemented and proven:

- fail-closed action allowlist
- repository path and symlink sandbox enforcement
- bounded changed-file and time-budget input
- public/elevated permission profiles
- write, shell, and untrusted-code refusal
- token-scope tests
- policy-change and malformed-config tests
- PR repository/number spoofing tests
- private-repository default refusal
- SSRF, port, redirect, and pagination protection
- public/private and credential leak controls
- temporary patch-workspace containment
- full live GitHub API ingestion proof

Detailed contract: [`36-production-hardening.md`](36-production-hardening.md).

## Phase 8 — Standalone product path

Status: in progress; Phase 8A self-hosted service is implemented and entering proof/release review.

### Phase 8A — Self-hosted service

Implemented:

- dependency-free HTTP service
- loopback-safe default binding
- bearer authentication for exposed binding
- bounded JSON API and rate limiting
- one configured repository workspace
- existing Command Center served from the installed package
- real review, mission, settings, state and report APIs
- HMAC-verified GitHub webhook intake
- webhook delivery replay suppression
- installed-wheel resource proof
- non-root/read-only/capability-dropped Docker deployment
- Docker Compose profile
- source, wheel and container proof workflow

Detailed contract: [`37-standalone-service.md`](37-standalone-service.md).

### Phase 8B — GitHub App delivery

Still required:

- GitHub App installation authentication
- installation and repository routing
- isolated read-only collector token service
- durable webhook delivery queue
- isolated comment/check poster with least write permission
- signed audit exports
- production reverse-proxy deployment

The collector, analyzer, reasoner and poster must remain separate trust zones.

### Later Phase 8 product work

- cloud dashboard
- organization rules
- enterprise/team review memory
- multi-repository service orchestration
- signed proof artifacts and audit export

## Current next step

Freeze and prove Phase 8A through normal CI, Main Review, standalone runtime proof, installed-wheel proof, hardened container proof and multiplatform packaging.

After Phase 8A is merged, continue with GitHub App installation and delivery as a separate trust-zone implementation rather than adding write authority to the reviewer runtime.
