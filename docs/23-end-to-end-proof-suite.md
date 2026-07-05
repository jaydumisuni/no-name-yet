# End-to-End Proof Suite

The end-to-end proof suite keeps moving when an external reviewer is unavailable.

It does not pretend an external reviewer reviewed the PR.

Instead, it proves every internal phase that must work before external review feedback can be useful.

## Command

```bash
main-review proof-suite --pretty
```

Inspection mode:

```bash
main-review proof-suite --no-fail --pretty
```

## Phases

The suite checks:

- final proof gate
- repository review verdict
- THETECHGUY verification standard
- diff-review path
- external review ingestion batch
- memory write loop using deterministic reviewer fixtures

## Why this exists

When an external reviewer is unavailable or rate-limited, we do not stop and we do not fake the result.

We move around the blocker by proving our own pipeline:

```text
CI
  ↓
clean clone proof
  ↓
final proof
  ↓
proof suite
  ↓
external review when available
```

## Rule

External review is valuable, but not a single point of failure.

Main Review must still prove:

- it can review a repository
- it can classify changed-file risk
- it can ingest reviewer-style comments
- it can write accepted lessons to memory
- it can fail loudly when evidence is missing

## Current limitation

The proof suite uses deterministic fixtures for external reviewer comments.

Real external reviewer comments should still be consumed when available.
