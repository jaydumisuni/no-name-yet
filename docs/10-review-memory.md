# Review Memory

Review Memory is the second implementation layer of Main Review.

Its purpose is to let the reviewer remember engineering decisions, lessons, principles, boundaries, and risks as structured records.

## Why memory matters

A normal reviewer starts from zero on every pull request.

Main Review should not.

It should remember:

- previous architecture decisions
- lessons from past mistakes
- accepted principles
- rejected approaches
- public/private boundaries
- known risk areas
- owner-approved standards

This is how the reviewer starts moving from generic review to project-aware engineering judgment.

## Memory record kinds

```text
decision   A chosen engineering direction.
lesson     A learned outcome from review, bug, incident, or correction.
principle  A reusable rule of thinking.
boundary   A project separation that should be protected.
risk       A known fragile or dangerous area.
```

## Memory status

```text
proposed    Useful but not yet fully verified.
verified    Accepted as trusted project knowledge.
superseded  Replaced by better evidence or a newer rule.
rejected    Considered and intentionally not accepted.
```

## CLI

Add a memory record:

```bash
main-review memory add \
  --kind principle \
  --title "Evidence over ego" \
  --summary "Conclusions change when stronger evidence appears." \
  --reason "The reviewer expects to be challenged." \
  --status verified \
  --tag humility \
  --tag evidence \
  --confidence 0.95
```

List records:

```bash
main-review memory list --pretty
```

Search records:

```bash
main-review memory search "architecture" --pretty
```

## Storage

Memory is stored locally in:

```text
.main-review/memory.json
```

This keeps v1 simple and portable. Later, the same schema can be backed by a database, API, or Hunter memory service.

## Trust rule

Memory is not absolute truth.

It is current best knowledge.

The reviewer must expect to be challenged. If stronger evidence appears, the memory should be refined instead of defended.

## Future direction

Later memory should support:

- references to PRs/issues/commits
- confidence changes over time
- supersession chains
- owner approval logs
- project-specific rule packs
- cross-repository lessons
- integration with Code Ops

## Current limitation

Patch 02 only stores and retrieves memory. It does not yet use memory to judge changes.

That comes later when the Verdict Engine is added.