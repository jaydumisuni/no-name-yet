# Retired PR Lesson Harvest — 2026-07-24

This is the required learning pass that precedes deletion of the historical branches listed in `docs/52-open-pr-closure-and-branch-retirement.md`.

Closing a pull request preserves its Git history, but preservation alone is not learning. Each retired PR was therefore classified as one of:

- **accepted lesson** — the generalized rule already has Sergeant-owned implementation, focused regressions, clean controls, and exact-head proof;
- **candidate / needs lineage** — the PR exposed a useful mechanism, but a verified fixing lineage, transfer controls, or hidden holdout is still missing;
- **benchmark only** — useful evidence for later evaluation, not a permanent rule;
- **duplicate / superseded** — the useful value is already present on `main` through a later merged PR;
- **no transferable lesson** — temporary observer or trigger infrastructure with no new engineering mechanism.

No closed PR, external reviewer comment, or historical branch was treated as authority merely because it existed.

## Accepted retrospective lessons

### 1. Cpl findings must be adjudicated, not multiplied

Sources: PRs #96 and #102.

The live ten-case council benchmark preserved full recall but exposed poor precision and verdict accuracy because model confirmations were counted as additional defects, advisory findings could influence the gate, failed passes were not reassigned, and rejected findings could leave stale verdicts.

Accepted rule:

> Reconcile model/Cpl findings against deterministic Sergeant evidence. Matching reports are confirmations, minor or unsupported reports remain advisory, and a novel blocker or major may gate only with verified evidence and independent support. Recompute the final verdict after adjudication and preserve raw reports separately for audit.

Permanent implementation and proof already exist on `main` in `main_review/cpl_council.py`, `main_review/cpl_noise.py`, `main_review/cpl_runtime.py`, `main_review/llm_review.py`, `main_review/pr_reviewer.py`, `main_review/review_benchmark.py`, and `tests/test_cpl_noise_governor.py`.

Lesson record: `.github/self-learning/lessons/cpl-adjudication-noise-20260724.json`.

### 2. Evidence-pipeline completeness is part of correctness

Sources: CodeRabbit battle lanes #124–#128 and repair PR #130.

The battle exposed that a review or learning pipeline can appear successful while its evidence is incomplete or ambiguous. The accepted boundaries are:

- retrieve all changed-file pages and fail closed at GitHub's 3,000-file API ceiling;
- reject malformed rows inside an otherwise valid file list;
- derive mandatory provenance from the case classification rather than a manifest opt-out;
- validate and propagate feature-enablement evidence flags;
- use non-cone sparse checkout when exact learned-closure paths are required;
- keep execution logs separate from machine-readable JSON summaries;
- never rewrite immutable historical scores while repairing the pipeline.

These boundaries were repaired, independently reviewed, regression-tested, and merged through PR #130.

Lesson record: `.github/self-learning/lessons/review-evidence-integrity-20260724.json`.

### 3. Preserve and replay before destructive cleanup

Source: PR #135.

Accepted rule:

> A successful copy is not deletion authority. Destructive cleanup requires a complete provenance ledger, matching byte length and digest, successful recovery replay, content-equivalence proof, and explicit owner authorization naming the exact item to delete.

The rule is implemented in `main_review/actions_evidence.py`, `scripts/validate_actions_evidence.py`, the preservation and replay ledgers, and `tests/test_actions_evidence.py`. The original preservation accounted for 29 artifacts and 13,772,291 bytes while authorizing zero deletions.

Lesson record: `.github/self-learning/lessons/preserve-before-delete-20260724.json`.

## Candidate lessons retained for governed follow-up

### PRs #106 and #107 — model-free editor battle lineage

PR #106 exposed the original immutable target, but the round was invalidated after its branch head moved. PR #107 replaced it using independently verified identical target bytes at exact head `ea8f1590fc6fb7c27eb363eb854f173678c60b00`, and CodeRabbit reviewed that replacement.

Two useful findings were preserved but are not promoted without fixing lineage and transfer proof:

1. a parse failure must not silently substitute an empty model that can later overwrite the user's valid document;
2. an expensive render path must not synchronously reload project context and catalogues on every keystroke.

Status: `needs_lineage`. Both PR numbers are recorded in the candidate artifact so the original and reviewed-replacement provenance remain explicit.

### PR #108 — model-assisted battle

Four useful mechanisms were preserved but remain candidates until generalized controls and unrelated transfer are proven:

1. a supposedly frozen workflow must compare actual base/head SHAs with the approved immutable SHAs;
2. a council proof must fail on review failure, incomplete council, provider errors, or unresolved final gaps;
3. nullable data must be checked before downstream persistence or notification calls;
4. duplicate-state comparison and update must be one atomic operation.

Status: `needs_lineage`.

### PR #133 — Hunter mobile proof

The evidence proves a reusable UI-review direction: critical mobile controls must be visible, non-overlapping, reachable, and behaviorally tested at the target viewport rather than inferred from source strings or desktop rendering.

The branch lacks a complete defective/fixing lineage suitable for permanent admission, so it is retained as `benchmark_only` rather than converted into a detector.

Candidate record: `.github/self-learning/retrospective-candidates-20260724.json`.

## Inspected PR dispositions

| PRs | Disposition | Reason |
|---|---|---|
| #141 | duplicate / superseded | Cross-repository intake and policy landed through PR #142 and current `main`. |
| #105 | duplicate / superseded | Permanent deterministic officers and tests landed through the later council/campaign integration. |
| #65, #47 | superseded release/documentation work | Current Command Center, packaging, README, and release state are newer. No unique defect lineage remains. |
| #132 | design reference | The stale 0.5.0 branch must be recut from current `main`; its old release plan is not training truth. |
| #96 | accepted through later correction | Generalized Cpl-noise lesson is recorded above and implemented through PR #102. |
| #133 | benchmark only | Useful responsive interaction proof, but no complete fixing lineage. |
| #124–#128 | accepted through later correction | CodeRabbit findings were verified and repaired through PR #130; no duplicate detector is added. |
| #118–#113 | evidence only | Trigger/closure lanes preserve frozen scores and artifacts; their mechanisms are already represented by the parent campaign and transfer modules. |
| #106/#107 | candidate with explicit lineage | PR #106 was the original invalidated battle; PR #107 reviewed identical target bytes and produced the retained findings. Fixing lineage and transfer proof are still required. |
| #108 | candidate | Workflow, null-ordering, and atomicity findings preserved; no automatic promotion. |
| #104, #97 | observer only | Comparison/certification observers add evidence, not a new transferable defect mechanism. |

## Deletion boundary

Historical branches are safe to delete only after this harvest PR is merged and its exact head passes the normal proof matrix. The candidate records must remain on `main`; deleting a branch must not delete the only copy of a useful finding.

Future work may promote a candidate only through the normal governed path:

```text
verified defective/fixing lineage
→ frozen blind review
→ generalized rule
→ positive and clean controls
→ unrelated transfer
→ hidden holdout
→ owner-controlled admission
```

Automatic promotion and automatic merge remain forbidden.