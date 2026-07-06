# Sergeant Branch Hygiene Audit

Status: initial safety audit created after the v1 release.

## Protected truth

Keep these refs untouched:

- `main` — released v1 baseline.
- `v1` — release tag.
- `archive/pre-cleanup-snapshot` — safety snapshot from current `main` before branch cleanup.
- `archive/v1-release-cleanup-anchor` — extra v1 cleanup anchor from current `main`.
- `v2-lab` — clean future branch for V2 work.
- `docs/branch-hygiene-audit` — this audit branch.

## Confirmed repository state before cleanup

- v1 release work is on `main`.
- README hero image and public identity are on `main`.
- `pyproject.toml` package discovery fix is on `main`.
- PR #34 head checks passed before merge.
- Final merge commit has no visible workflow run attached, so PR proof and content verification are the proof source for that release polish.

## Cleanup rule

Do not delete branches blindly.

Delete only branches that are clearly abandoned scratch/retry branches after confirming they are not the current `main`, release tag, V2 branch, or audit/archive branch.

## Obvious cleanup candidates reported by branch audit

These branch-name patterns should be treated as cleanup candidates:

- `do-not-use*`
- `mistake*`
- `last-mistake*`
- `please-ignore*`
- `*ignore*`
- `*loop*`
- `why-am-i-doing-this*`
- `stop-branching-now*`
- `noop*`
- `tmp*`
- duplicate retry families such as `sentinel-trust-checks-v*`, `srg-review-intelligence-v*`, and `trust-checks-v*`

## Branch categories

| Category | Action |
| --- | --- |
| release truth | keep |
| archive anchor | keep |
| active future work | keep |
| merged PR branch | delete after confirmation |
| obvious failed loop/scratch branch | delete after confirmation |
| unknown branch with unique commits | compare before deleting |

## Next steps

1. Export full branch list locally with `git branch -r` or from GitHub branches page.
2. Paste or commit the list into this document.
3. Mark each branch `keep`, `delete`, or `unknown`.
4. Delete only `delete` branches.
5. Compare every `unknown` branch against `main` before deleting.
