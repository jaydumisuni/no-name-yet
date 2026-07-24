# Open PR Closure and Branch Retirement — 2026-07-24

This record closes the historical Sergeant pull-request backlog so retired branches can be deleted without losing useful work.

GitHub pull-request pages remain the permanent reference for the closed PR's commits, diffs, review discussions, and exact head SHA even after the named head branch is deleted. Durable training artifacts remain in the recorded Google Drive evidence locations.

## Integrated or superseded by current `main`

- **#141 — external-repository learning memory:** superseded by `AGENTS.md`, `docs/51-cross-repository-learning-intake.md`, `main_review/cross_repo_learning.py`, the governed source registry, tests, and the completed Week 1 records now on `main`.
- **#105 — deterministic permanent-officer council:** superseded by the permanent officer implementation, doctrine, tests, and campaign integration on `main`.
- **#65 — Sergeant 0.3.2 Command Center hardening:** superseded by later integrated Command Center and 0.4.1 work.
- **#47 — V2 public wording:** superseded by current README, CLI branding, and later release documentation.

## Retire and recreate from current `main` when needed

- **#132 — Sergeant 0.5.0 release candidate:** do not merge the stale 426-commit candidate. A future 0.5.0 release branch must be cut from the current `main` after project-driven learning and release authorization. The PR remains the historical release-planning reference.
- **#96 — Cpl finding adjudication experiment:** do not merge the old diverged implementation. Preserve the PR as a future design reference for model-council adjudication if models are re-enabled; any production version must be rebuilt against current Cpl, officer, and evidence contracts with fresh tests and proof.

## Historical evidence and observer PRs — never merge

- **#133** Hunter mobile header/notification evidence.
- **#128, #127, #126, #125, #124** CodeRabbit transfer battle lanes.
- **#118, #117, #116, #115, #114, #113** isolated transfer evidence and learned-closure lanes.
- **#106** immutable model-free battle round 1.
- **#104** PR #103 reviewer-comparison observer.
- **#97** certified-roster benchmark observer.

These PRs were explicitly created as evidence-only, observer, battlefield, or do-not-merge branches. Their useful history remains in the closed PR pages and previously preserved evidence. They must not be merged into product `main`.

## Retirement rule

After every PR listed above is closed, its head branch and any private base branch used only by that PR may be deleted. Keep `main` as the only permanent branch. Create temporary feature, proof, release, or learning branches only for active work, and delete them after merge or documented closure.

## Canonical checkpoint

At the time of this cleanup, controlled self-learning Week 1 was merged through PR #136 with merge commit `32b50050779751f825b15e25a2af518e5e3b27af`. The accepted Lumi credential-origin lesson, seven counted rounds, blocked duplicate attempt, zero automatic promotions, and zero automatic merges are preserved on `main`.
