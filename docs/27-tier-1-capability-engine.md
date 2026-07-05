# Tier 1 Capability Engine

Sergeant's Tier 1 capability engine moves review from file scanning toward system review.

## Active capabilities

- Cross-file dependency reasoning
- Architecture review
- Data-flow analysis
- Call graph understanding
- Security taint analysis
- Performance analysis
- Concurrency/race detection
- API contract verification
- Test impact analysis
- Regression prediction
- Multi-language scanner-backed review

## Rule

The engine is static-first and does not execute repository code.

It reports evidence-backed review signals and leaves the final verdict to Sergeant's review pipeline.

## CLI

```bash
main-review capability-review . --files "src/api.js,src/db.js" --pretty
```

## Exit condition

Tier 1 is considered active when the capability engine is wired into Sergeant PR review, covered by tests, and visible in review markdown.