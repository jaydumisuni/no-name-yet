# Cpl Finding Adjudication

## Purpose

Cpl supplies independent reasoning and officer support, but model reports must not multiply an already-proven Sergeant defect or override deterministic severity merely by using stronger wording.

This boundary separates:

- raw Cpl findings and model passes;
- confirmations of existing deterministic evidence;
- grounded novel Cpl findings admitted to the merge gate;
- advisory suggestions;
- rejected or insufficiently supported claims.

Sergeant remains the final authority. Deterministic repository, diff, capability, runtime, and proof evidence retain gate authority.

## Evidence flow

1. Sergeant produces deterministic findings.
2. Cpl and its officer-support passes independently inspect the supplied evidence.
3. Cpl merges equivalent model reports within the council.
4. The adjudication layer compares the merged Cpl findings with deterministic findings by normalized path, bounded line distance, root-cause identity, and meaningful defect-level evidence overlap.
5. Family and line proximity alone are not enough to merge two findings. Adjacent defects remain distinct unless they share the same root cause or sufficient evidence identity.
6. A matching Cpl report becomes a confirmation. It adds model provenance but does not create another user-facing defect or raise deterministic severity.
7. A genuinely new blocker or major finding may be admitted only when:
   - its evidence was verified against supplied repository text;
   - it names a supplied path and valid supplied line range;
   - it has the required independent model support for the active formation;
   - it is not merely a generic test or documentation request.
8. Minor, note, tests, and documentation suggestions remain advisory unless a deterministic proof or policy independently promotes them.
9. Rejected and advisory reports remain visible for audit and later Judge/human evaluation. They are not silently erased.

## Council gaps

Unresolved council state is preserved, but not every gap controls the merge verdict.

### Verdict-affecting assurance gaps

- a planned required report is still missing;
- a finding-dependent gap is tied to an admitted actionable finding;
- an admitted actionable recurrence remains unresolved;
- an unanswered question carries an explicit `required_assurance: true` field.

### Confidence-only gaps

- one optional provider/member failed while the formation continued;
- council wording or non-gating verdicts disagree;
- an unanswered question does not explicitly declare required assurance;
- a raw recurrence or confirmation gap belongs only to a confirmation, advisory, or rejected finding.

Words such as `test`, `evidence`, `security`, or `verification` inside free-form question text do not promote the question into a verdict gap. The structured flag controls that decision.

Confidence-only gaps reduce confidence and keep the council visibly incomplete, but they do not convert a clean `PASS` into `NEEDS WORK` by themselves.

## Public result fields

Cpl exposes:

- `verdict` — final post-gap Cpl verdict after finding adjudication and verdict-affecting council-gap gating;
- `raw_verdict` — verdict derived from raw merged Cpl reports before deterministic reconciliation;
- `findings` — admitted novel actionable Cpl findings;
- `raw_findings` — raw effective Cpl findings before cross-source admission; these may later become confirmations, advisory findings, or rejected findings;
- `confirmations` — Cpl reports matching deterministic findings;
- `advisory_findings` — non-gating suggestions;
- `rejected_findings` — grounding/support failures kept for audit;
- `adjudication` — counts, rule, dispositions, and supporting-model requirement;
- `council.final_gaps` — all unresolved raw council gaps retained for audit;
- `council.adjudicated_final_gaps` — gaps remaining after finding-dependent admission control;
- `council.suppressed_finding_gaps` — raw recurrence or confirmation gaps that cannot gate because the associated finding was not admitted;
- `council.verdict_gaps` — adjudicated unresolved gaps that may affect the verdict;
- `council.confidence_gaps` — adjudicated uncertainty that affects confidence only;
- `council.informational_gaps` — other preserved context;
- `council.effective_findings` — raw council findings used for council-specific proof;
- `council.adjudicated_findings` — admitted novel Cpl findings used by the final reviewer.

The focused provider-certification path still inspects raw council findings and actual completed model passes. Cross-source adjudication therefore cannot fabricate model independence or hide a failed provider proof.

## Safety and rollback

This change does not grant write, merge, shell, network-discovery, or repository-execution authority.

Rollback removes:

- `main_review/finding_adjudication.py`;
- the adjudication call and gap classification in `main_review/cpl_runtime.py`;
- focused adjudication tests;
- this document.

The deterministic reviewer, provider routes, raw Cpl passes, and existing council proof remain available after rollback.
