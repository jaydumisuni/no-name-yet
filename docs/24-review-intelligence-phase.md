# Review Intelligence Phase

This phase adds the reviewer behavior that was still missing after the proof gate.

## Included

- Decision workspace: every external review comment becomes an explicit decision.
- Engineering standard engine: checks proof evidence and claims against implementation.
- Challenge mode: asks whether the conclusion is properly supported.
- Multi-reviewer consensus: combines Main Review, external reviewers, and human notes by evidence instead of vote count.

## Decision workflow

```text
external comment
  -> classification
  -> fix / consider / reject / save_pattern
  -> optional memory candidate
```

## Confidence condition

This phase is considered working only when tests pass and the clean-clone proof still passes.