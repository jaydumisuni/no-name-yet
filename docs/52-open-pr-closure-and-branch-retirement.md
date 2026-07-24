# Open PR Closure and Branch Retirement — 2026-07-24

This record closes the historical Sergeant pull-request backlog so retired branches can be deleted without losing useful work.

GitHub pull-request pages remain the permanent reference for the closed PR's commits, diffs, review discussions, and exact head SHA even after the named head branch is deleted. Durable training artifacts remain in the recorded Google Drive evidence locations.

Closing and preserving history are not sufficient by themselves. Before branch deletion, the retired PRs must also pass the lesson-harvest classification in `docs/53-retired-pr-lesson-harvest.md`: proven transferable value becomes a Sergeant-owned accepted lesson, incomplete value becomes a governed candidate or benchmark, and duplicate/noise is rejected with a reason.

## Integrated or superseded by current `main`

- **#141 — external-repository learning memory:** superseded by `AGENTS.md`, `docs/51-cross-repository-learning-intake.md`, `main_review/cross_repo_learning.py`, the governed source registry, tests, and the completed Week 1 records now on `main`.
- **#105 — deterministic permanent-officer council:** superseded by the permanent officer implementation, doctrine, tests, and campaign integration on `main`.
- **#96 — Cpl finding adjudication experiment:** the proven finding-reconciliation and noise-governance lesson was implemented and merged through PR #102. The old diverged branch must not be merged, but its generalized lesson is preserved in `.github/self-learning/lessons/cpl-adjudication-noise-20260724.json`.
- **#65 — Sergeant 0.3.2 Command Center hardening:** superseded by later integrated Command Center and 0.4.1 work.
- **#47 — V2 public wording:** superseded by current README, CLI branding, and later release documentation.

## Retire and recreate from current `main` when needed

- **#132 — Sergeant 0.5.0 release candidate:** do not merge the stale 426-commit candidate. A future 0.5.0 release branch must be cut from the current `main` after project-driven learning and release authorization. The PR remains the historical release-planning reference.

## Historical evidence and observer PRs — never merge

- **#133** Hunter mobile header/notification evidence — preserved as a benchmark-only learning candidate.
- **#128, #127, #126, #125, #124** CodeRabbit transfer battle lanes — their verified integrity findings were repaired through PR #130 and are preserved in `.github/self-learning/lessons/review-evidence-integrity-20260724.json`.
- **#118, #117, #116, #115, #114, #113** isolated transfer evidence and learned-closure lanes.
- **#106/#107** immutable model-free battle round 1 — useful editor findings are retained as `needs_lineage` candidates.
- **#108** model-assisted battle — useful workflow, null-ordering, and atomicity findings are retained as `needs_lineage` candidates.
- **#104** PR #103 reviewer-comparison observer.
- **#97** certified-roster benchmark observer.

These PRs were explicitly created as evidence-only, observer, battlefield, or do-not-merge branches. Their product diffs must not be merged merely to preserve them. Useful findings are instead retained in the accepted lesson or candidate records named above.

## Retirement rule

A historical head branch and any private base branch used only by it may be deleted only after:

1. the PR is closed or merged according to its intended role;
2. its commits, discussion, head SHA, and durable artifacts remain recoverable;
3. its transferable value has been classified by the lesson harvest;
4. every accepted lesson is represented by Sergeant-owned code/tests and exact-head proof;
5. every incomplete useful finding is retained as a candidate or benchmark with missing gates stated;
6. the harvest PR itself is merged to `main`.

Keep `main` as the only permanent branch. Create temporary feature, proof, release, or learning branches only for active work, and delete them after merge or documented closure and lesson harvest.

## Canonical checkpoint

At the time of the original cleanup, controlled self-learning Week 1 was merged through PR #136 with merge commit `32b50050779751f825b15e25a2af518e5e3b27af`. The accepted Lumi credential-origin lesson, seven counted rounds, blocked duplicate attempt, zero automatic promotions, and zero automatic merges are preserved on `main`.

The retirement decision becomes complete only after the retrospective lesson harvest is merged. Until then, branch deletion is not authorized by this document.