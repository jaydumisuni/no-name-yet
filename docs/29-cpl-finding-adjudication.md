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
4. The adjudication layer compares the merged Cpl findings with deterministic findings by normalized path, bounded line distance, root-cause identity, and compatible evidence family.
5. A matching Cpl report becomes a confirmation. It adds model provenance but does not create another user-facing defect or raise deterministic severity.
6. A genuinely new blocker or major finding may be admitted only when:
   - its evidence was verified against supplied repository text;
   - it names a supplied path and line range;
   - it has the required independent model support for the active formation;
   - it is not merely a generic test or documentation request.
7. Minor, note, tests, and documentation suggestions remain advisory unless a deterministic proof or policy independently promotes them.
8. Rejected and advisory reports remain visible for audit and later Judge/human evaluation. They are not silently erased.

## Council gaps

Unresolved council state is preserved, but not every gap controls the merge verdict.

### Verdict-affecting assurance gaps

- a planned required report is still missing;
- a high-impact finding still lacks required independent confirmation;
- a verified recurrence remains unresolved;
- an unanswered question explicitly identifies missing required evidence, runtime proof, verification, tests, security, authorization, permission, credential, or equivalent assurance.

### Confidence-only gaps

- one optional provider/member failed while the formation continued;
- council wording or non-gating verdicts disagree;
- a low-risk contextual or preference question remains unanswered.

Confidence-only gaps reduce confidence and keep the council visibly incomplete, but they do not convert a clean `PASS` into `NEEDS WORK` by themselves. Required assurance questions remain verdict-affecting even when they are represented as unanswered questions.

## Public result fields

Cpl exposes:

- `verdict` — adjudicated Cpl gate verdict;
- `raw_verdict` — verdict derived from raw merged Cpl reports before deterministic reconciliation;
- `findings` — admitted novel actionable Cpl findings;
- `raw_findings` — all effective grounded Cpl findings before cross-source adjudication;
- `confirmations` — Cpl reports matching deterministic findings;
- `advisory_findings` — non-gating suggestions;
- `rejected_findings` — grounded/support failures kept for audit;
- `adjudication` — counts, rule, dispositions, and supporting-model requirement;
- `council.verdict_gaps` — unresolved gaps that may affect the verdict;
- `council.confidence_gaps` — unresolved uncertainty that affects confidence only;
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