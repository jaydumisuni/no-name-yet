# Memory Write Loop

Patch 07 closes the first learning loop.

Patch 06 could ingest external reviewer comments and export learning candidates.

Patch 07 can write those learning candidates into Review Memory.

## Principle

```text
External review comment
  ↓
Classify
  ↓
Survives scrutiny
  ↓
Write as proposed memory
  ↓
Human verifies or rejects later
```

## CLI

```bash
main-review learn-review coderabbit-comments.json --pretty
```

Write only candidates with a matching tag:

```bash
main-review learn-review coderabbit-comments.json --tag security --pretty
```

Write with verified status when a human has already approved the batch:

```bash
main-review learn-review coderabbit-comments.json --status verified --pretty
```

## Default status

Learning candidates are written as `proposed` by default.

That matters because the reviewer expects to be challenged. A CodeRabbit/Qodo/PR-Agent comment is not automatically truth.

It becomes trusted only after it survives scrutiny.

## Why this matters

This preserves review history from earlier work.

Every useful external reviewer signal can become structured memory:

- lesson
- principle
- evidence link
- tags
- affected path/module
- confidence

## Current limitation

Patch 07 writes all accepted candidates from a JSON file. It does not yet provide an interactive classification UI.

That comes later.