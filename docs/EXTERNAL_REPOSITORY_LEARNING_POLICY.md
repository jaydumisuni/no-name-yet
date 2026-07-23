# External Repository Learning Policy

Sergeant may learn from useful engineering activity that happens outside the Sergeant repository. THETECHGUY repositories and suitable public repositories are valid discovery sources when their evidence can be pinned, replayed, and evaluated without contaminating blind review.

## Discovery signals

Candidate inputs include defect-fixing commits, verified review corrections, failed workflows followed by grounded repairs, integrity or security corrections, reusable negative results, and repeated defect patterns across repositories or languages.

A notification, commit, bot comment, script execution, or green workflow is only a signal. It is not itself a lesson.

## Minimum candidate record

- source repository;
- defective or pre-fix commit;
- fixing commit;
- source PR or issue when available;
- language and changed files;
- classification: defect fix, workflow repair, review correction, formatting-only, feature, or unknown;
- exact source lineage;
- ownership or licence;
- Sergeant blind-review freeze commit;
- artifact SHA-256;
- durable evidence location.

## Admission sequence

```text
discover external activity
→ classify whether it contains a real learning opportunity
→ pin pre-fix and fixing states
→ collect only authorized files and context
→ freeze Sergeant's blind review before fix disclosure
→ reveal and verify fixing truth
→ derive a generalized candidate lesson
→ Teacher proposes
→ Prosecutor challenges scope and root cause
→ Defender builds clean negative controls and overfitting attacks
→ test transfer on unrelated repositories or languages where appropriate
→ run hidden holdout
→ admit only proven transferable value
```

## Outcomes

- **Admit:** convert the verified lesson into Sergeant-owned detector code, tests, proof rules, benchmarks, tools, or durable memory.
- **Benchmark only:** useful for evaluation but not general enough for a permanent detector.
- **Negative control:** proves that a tempting pattern should not be flagged.
- **Reject:** formatting-only, generated noise, feature work without a defect boundary, unverifiable provenance, contaminated blind evidence, or repository-specific overfitting.

## Boundaries

1. Never expose fixing truth before the blind result is frozen.
2. Never treat a bot, external model, reviewer, or successful workflow as authority by itself.
3. Never claim learning from formatting-only or generated changes without an independently verified defect boundary.
4. Preserve rejected lessons and reasons.
5. Preserve exact repository, commit, file, language, ownership/licence, and artifact provenance.
6. No automatic promotion or merge during controlled learning.
7. Useful external value must become Sergeant-owned doctrine, tests, benchmarks, tools, or memory rather than an unexamined dependency.
8. Sergeant remains final admission authority.

## THETECHGUY intake

Owned repositories such as TechGuyCheckm8, lumi-dm, Hunter, TechGuy Tool, TechGuy DM, TechGuy IMEI, and related projects are first-class discovery sources. Prioritize transferable boundaries such as unsafe state transitions, missing validation, concurrency races, data-loss risks, weak provenance, release-integrity failures, security mistakes, non-idempotent money operations, broken recovery, and false-success handling.

Routine formatting, naming, generated assets, and repository-specific product behaviour should normally remain outside permanent Sergeant knowledge unless they reveal a broader proven rule.