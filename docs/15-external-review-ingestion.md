# External Review Ingestion

Patch 06 starts the ingestion foundation for external reviewer comments.

The goal is not to obey external reviewers.

The goal is to classify their comments and turn useful survivors into Main Review learning material.

## Classification outcomes

```text
🟢 correct       Fix immediately.
🟡 suggestion    Consider if it fits our architecture.
🔴 reject        Do not apply; document why.
🧠 save_pattern  Convert into reviewer learning material.
unclassified     Needs human classification.
```

## Input format

`main-review ingest-review` accepts a JSON file:

```json
{
  "comments": [
    {
      "source": "coderabbit",
      "body": "Missing receiver validation test.",
      "repository": "jaydumisuni/demo",
      "pr_number": 7,
      "path": "src/api.py",
      "line": 42,
      "classification": "🟢",
      "reason": "This is a real contract gap.",
      "tags": ["testing", "contract"],
      "url": "https://example.test/comment/1"
    }
  ]
}
```

A plain list of comment objects is also accepted.

## CLI

```bash
main-review ingest-review coderabbit-comments.json --pretty
```

## Output

The output includes:

- summary counts
- normalized comments
- learning candidates

Learning candidates can later be written into Review Memory.

## Why this exists

We have already used external reviews many times across different project chats and repos.

That history should not be lost.

Every external reviewer comment that survives our scrutiny becomes training material for Main Review.

## Current limitation

Patch 06 does not fetch GitHub comments directly yet.

It ingests exported/copied JSON first so the classification and learning pipeline can be tested without GitHub permissions or reviewer-specific API assumptions.

## Next direction

Later patches should add:

- GitHub PR comment collector
- reviewer author/source detection
- inline review comment export
- classification UI/table
- memory-write command for accepted learning candidates
- batch ingestion across the three hackathon repos

## Guiding rule

> External reviewers are training material, not final authority.
