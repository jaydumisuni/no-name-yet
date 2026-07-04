# GitHub PR Comment Collector

Patch 08 adds the first GitHub PR comment collector foundation.

It normalizes exported GitHub PR comments into the same ingestion JSON shape used by Main Review.

## Principle

```text
GitHub comments are raw material.
Classification still comes after collection.
```

The collector does not decide whether a comment is correct.

It only preserves the comment, source, author, path, line, URL, repository, PR number, and tags.

## CLI

```bash
main-review collect-github-comments github-comments.json \
  --repository jaydumisuni/no-name-yet \
  --pr-number 7 \
  --pretty
```

Output can be passed into the existing ingestion/classification flow.

## Source detection

The collector detects common review sources from author/body text:

- CodeRabbit
- Qodo / PR-Agent
- reviewdog
- GitHub Actions
- generic GitHub/manual comments

## Why no network in v1

Patch 08 keeps the core logic testable and connector-independent.

The GitHub connector or a future app bridge can fetch PR comments and save the raw JSON. Main Review then normalizes that JSON safely.

## Future direction

Later patches should add:

- direct GitHub PR fetch bridge
- batch collector across repos
- CodeRabbit-specific classifier hints
- comment-to-classification workspace
- unresolved/resolved thread state
- automatic learning candidate export after classification

## Workflow

```text
GitHub PR comments
  ↓
collect-github-comments
  ↓
ingest-review
  ↓
manual classification
  ↓
learn-review
  ↓
Review Memory
```
