# Diff Review Mode

Diff Review Mode is the fifth implementation layer of Main Review.

It reviews a changed-file list instead of the full repository state.

This is the first step toward PR-aware review.

## Principle

```text
The impact of a change is not measured only by line count.
Changed paths reveal review risk.
```

## CLI

Review a copied changed-file list:

```bash
main-review diff-review --files "src/app.py,tests/test_app.py" --pretty
```

Review `git diff --name-only` output:

```bash
git diff --name-only main...HEAD > changed.txt
main-review diff-review --file-list changed.txt --pretty
```

## Current checks

Patch 05 classifies changed files by:

- language
- role
- high-risk path

Then it produces early findings:

| Condition | Finding |
|---|---|
| No changed files provided | Major finding |
| High-risk path changed | Major finding |
| Source changed without tests | Major finding |
| Docs-only change | Note |

## Why this matters

Repository review tells us the current state.

Diff review tells us what changed.

A useful PR reviewer needs both.

## Safety rule

Diff Review Mode does not execute code.

It only inspects file paths and changed-file metadata.

## Future direction

Later versions should add:

- GitHub PR collector
- patch hunk parser
- changed-line context
- memory-aware path rules
- ownership/risk maps
- contract-change detection
- docs/code drift detection
- external review learning pattern matching

## Current limitation

Patch 05 does not fetch PRs from GitHub directly.

It accepts local changed-file lists first so the logic can stay testable and provider-independent.