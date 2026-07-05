# Review Batch Workflow

Patch 09 adds a single local batch workflow for external review learning.

It connects the earlier pieces:

```text
GitHub PR comments export
  ↓
collect-github-comments
  ↓
ingest-review
  ↓
optional learn-review
  ↓
Review Memory
```

## CLI

Preview a batch:

```bash
main-review review-batch github-comments.json \
  --repository jaydumisuni/no-name-yet \
  --pr-number 8 \
  --summary-only \
  --pretty
```

Write accepted/pre-classified learning candidates to memory:

```bash
main-review review-batch github-comments.json \
  --write-memory \
  --root . \
  --status proposed \
  --pretty
```

Filter memory writes by tag:

```bash
main-review review-batch github-comments.json \
  --write-memory \
  --tag security \
  --pretty
```

## Why this matters

Before Main Review can be trusted on harder review work, we need a repeatable way to consume external reviewer comments and preserve useful patterns.

Patch 09 makes that workflow one command instead of several manual steps.

## Important rule

Unclassified comments do not become memory.

A comment must be classified as useful first:

- correct
- save_pattern

Then it can become a memory candidate.

## Current limitation

This still expects exported/copied GitHub comments JSON.

Direct GitHub API fetching can sit above this later.
