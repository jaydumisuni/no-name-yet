# Cpl Noise Governor and Route Failover

## Status

Implemented as an additive layer between Cpl's raw council output and Sergeant's final action/consensus surface.

Cpl still records every grounded model finding, council pass, resolution, and route event. The governor does not hide or delete the audit trail. It separates evidence that strengthens an existing Sergeant finding from evidence that creates a genuinely new action.

## Why this layer exists

A multi-model council can be useful without every model report becoming a separate review comment.

The same defect may already be present in deterministic Sergeant evidence and then be independently confirmed by Cpl with different wording, category names, or a nearby line range. Counting each confirmation as another defect increases noise, lowers precision, and can make a satisfied review appear less reliable than it is.

The governor therefore distinguishes:

- independent confirmation of an existing deterministic finding;
- model-only advisory information;
- a novel independently supported defect;
- a grounded but not yet independently supported high-impact claim.

Evidence remains visible in all four cases.

## Cross-source reconciliation

Cpl findings are compared with deterministic repository, diff, capability, and review-intelligence findings using:

- normalized repository path;
- deterministic root-cause family;
- overlapping or nearby line ranges;
- existing precise council finding matching where available.

Examples of normalized families include unsafe data flow, unsafe file access, authorization gaps, secret exposure, architecture boundaries, proof gaps, change impact, and category-specific runtime risk.

A specific `shell=True` command-execution report can therefore confirm the deterministic unsafe-data-flow finding at the same sink without being emitted as a third action. Distant findings or findings from different root-cause families remain separate.

## Classification contract

`cpl_review` retains its original raw `findings` and adds:

```text
actionable_findings
confirmed_findings
advisory_findings
unconfirmed_findings
decision_findings
decision_verdict
noise_governor
route_failovers
```

### Deterministic confirmation

A grounded Cpl finding that overlaps existing deterministic evidence is stored in `confirmed_findings`.

It strengthens the audit record but does not create another required action or another benchmark prediction.

### Advisory

A model-only `minor` or `note` finding is stored in `advisory_findings`.

It remains visible for engineering judgment but does not downgrade the final decision by itself.

### Novel actionable finding

A novel grounded finding becomes actionable when:

- it is a verified blocker; or
- it is a verified major finding supported by at least two distinct completed model passes.

These findings enter `actionable_findings`, required actions, consensus evidence, and the final decision surface.

### Novel unconfirmed finding

A grounded blocker/major claim that has not yet satisfied the independent-support contract remains in `unconfirmed_findings`.

It is not presented as a proven additional defect. It can preserve `NEEDS WORK` uncertainty until another council member confirms, narrows, or rejects it.

## Verdict reconciliation

Council follow-up can confirm, reject, or narrow an earlier finding.

When a finding is rejected or removed from an effective pass, the pass verdict is recomputed from the findings that remain. A stale `BLOCK` or `NEEDS WORK` value cannot continue influencing Sergeant after its only supporting finding has been disproved.

Sergeant uses `decision_verdict` and `actionable_findings` for final required actions and consensus. The raw model verdict and raw findings remain visible for audit and comparison.

## Route failover

A selected model is not the officer and is not allowed to collapse the officer pass merely because its route fails.

For primary, specialist, and recruited follow-up passes, Cpl tries the remaining configured council models in bounded roster order before reporting the pass as failed.

Successful reassignment records:

```text
route_failovers[].pass
route_failovers[].failed_models
route_failovers[].completed_by
```

Follow-up recruitment records the corresponding `failover_from` list.

If every configured model fails, the pass remains failed and Sergeant preserves the required-route error honestly. The final error exposes only a safe category summary such as `http_429=2`, `timeout=1`, or `response_contract=1`; upstream response bodies are not copied into the council packet.

## Benchmark behavior

The blind quality benchmark measures the governed action surface:

- deterministic findings remain predictions;
- Cpl confirmations are not duplicate predictions;
- advisories are not actionable predictions;
- novel qualified Cpl findings remain predictions;
- raw council evidence stays available when packets are included.

The governor does not lower precision or recall thresholds and does not load expected benchmark answers before review. It changes only how already-generated evidence is classified after the review returns.

## Safety boundaries

- Deterministic Sergeant evidence remains authoritative.
- Raw Cpl evidence is never deleted from the packet.
- Model-only high-impact findings still require verified repository evidence.
- Novel major findings require independent model support before becoming additional actions.
- Verified blockers remain conservative and actionable.
- Provider failures remain visible when the complete roster cannot satisfy a pass.
- No model or failover route gains repository write, merge, or execution authority.
