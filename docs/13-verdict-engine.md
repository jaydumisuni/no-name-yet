# Verdict Engine

The Verdict Engine is the fourth implementation layer of Main Review.

Its job is to convert normalized evidence into the first machine decision:

```text
PASS
NEEDS WORK
BLOCK
```

## Principle

```text
Evidence decides the verdict.
The verdict does not invent evidence.
```

Patch 04 does not use AI yet. It uses deterministic severity rules so the foundation is testable and predictable.

## Verdict rules in v1

| Evidence state | Verdict |
|---|---|
| Any blocker finding | BLOCK |
| No blockers, at least one major finding | NEEDS WORK |
| Only minor/note findings | PASS |
| No findings | PASS |

## CLI

```bash
main-review review --pretty
```

This command runs:

```text
Repository scanner
  ↓
Evidence providers
  ↓
Verdict engine
```

## Output shape

```json
{
  "verdict": {
    "verdict": "NEEDS WORK",
    "reason": "Major evidence was found...",
    "suggested_next_action": "Resolve major findings..."
  },
  "evidence": {
    "finding_count": 1,
    "findings": []
  }
}
```

## Why deterministic first

AI reasoning comes later.

The first verdict engine must be simple enough to test and hard to fool:

- blockers block
- major issues require work
- minor issues do not stop progress

This gives Hunter and Code Ops a stable review target before AI reasoning is introduced.

## Future direction

Later versions will add:

- memory-aware verdicts
- project-specific severity rules
- architecture boundary checks
- external review learning patterns
- confidence weighting
- PR diff mode
- AI reasoning as an evidence interpreter, not unchecked authority

## Current limitation

Patch 04 reviews repository state, not pull request diffs.

PR-aware verdicts come later.