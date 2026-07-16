# Deterministic Permanent-Officer Formation

## Status

Implemented as the canonical adjudication path for independent pull-request review.

The permanent officers are Sergeant's review system. Models are optional support engines. A provider outage, exhausted quota, missing credential, or owner-disabled model route must reduce available amplification without erasing the council or turning the officers into labels around precomputed scanner output.

## Command path

```text
Repository and changed scope
        ↓
Deterministic evidence and bounded field investigations
        ↓
Cpl coordinates permanent-officer packets
        ↓
Analyst reconciles root causes
        ↓
Challenger attacks claims and preserves falsifiers
        ↓
Judge admits, advises, or rejects each claim
        ↓
Hermes delivers the canonical ledger to Sergeant
        ↓
Sergeant issues the final review verdict
```

Models may attach evidence to the responsible officer packet before adjudication. They do not create the officer, replace the officer, or vote directly on the final verdict.

## Permanent formation

Every review returns a report for all ten permanent officers:

| Officer | Deterministic responsibility |
| --- | --- |
| Quartermaster | Records available deterministic capacity, model-support state, and whether project code was executed. |
| Scout | Maps readable changed scope and records bounded coverage. |
| Engineer | Investigates correctness, architecture, contracts, cross-file behavior, and proof impact. |
| Medic | Investigates security boundaries, tainted data, unsafe file access, secrets, and recovery obligations. |
| Mechanic | Investigates runtime state, concurrency, lifecycle, and performance risks. |
| Analyst | Reconciles surviving findings into root-cause groups. |
| Challenger | Records the falsifiers checked and attacks both admitted and non-admitted claims. |
| Archivist | Preserves the evidence disposition for verified-experience processing; it does not promote raw claims. |
| Judge | Owns admission and required-assurance disposition. |
| Hermes | Preserves the mission, evidence, adjudication, assurance, and ground-report transactions. |

## Evidence admission

Raw scanners, path-risk rules, model responses, and historical recurrence are evidence inputs. They are not independent votes.

Judge records each claim as one of:

- `actionable` — grounded blocker or major evidence that may gate;
- `advisory` — useful non-gating evidence;
- `risk_trigger` — a request for named assurance, not a defect by itself;
- `confirmation` — model support for an existing deterministic claim;
- `duplicate` — repeated evidence for an existing root claim;
- `rejected_unsubstantiated` — insufficiently grounded evidence.

Only admitted actionable findings and unresolved explicit assurance obligations can force `NEEDS WORK` or `BLOCK`.

## Explicit assurance

A high-risk path does not fail merely because its filename is sensitive. It creates an explicit `required_assurance` record.

For the current deterministic formation, a readable high-risk change is satisfied when Scout maps it and Engineer, Medic, and Mechanic complete their bounded coverage. If required changed content cannot be inspected, the assurance remains unresolved and may gate. The result packet records the requirement, status, evidence, and whether it gates.

Free-form words such as “test” or “evidence” do not silently promote ordinary uncertainty into a blocker.

## Model amplification

When Cpl has a qualified route, model findings enter the same officer packets:

- independently supported novel blocker or major evidence can be tabled as actionable;
- deterministic confirmation remains visible without creating a duplicate action;
- model-only minor evidence remains advisory;
- unsupported novel major evidence remains auditable but cannot gate;
- provider failure changes `model_support_status`; it does not remove the permanent formation.

The default product policy therefore remains useful offline. An owner may still select a strict model-required policy for a particular release gate; that is an explicit policy choice, not a hidden architectural dependency.

## Result contract

`officer_council` is the canonical formation packet. It includes:

- `raw_findings` — collected claims before Judge disposition;
- `admitted_findings` and `actionable_findings` — grounded verdict-capable claims;
- `advisory_findings` and `rejected_findings` — auditable non-gating claims;
- `required_assurances` and `unresolved_assurances`;
- one report per permanent officer;
- the Hermes transaction ledger;
- `models_required: false` and the actual model-support status;
- the formation verdict recommendation and required actions.

Sergeant consensus consumes the canonical officer ledger. It does not count the repository scanner, diff policy, capability engine, or model council as separate votes for the same claim.

## Regression standard

The deterministic path must prove both signal and restraint:

- command injection;
- path traversal;
- authorization gaps;
- unsafe SQL data flow;
- API and proof contracts;
- architecture boundaries;
- concurrency;
- performance;
- the ten root defect classes recovered from the frozen PR comparison;
- clean and safe counterparts with no false verdict gate.

The blind benchmark scores Judge's reportable ledger rather than raw pre-adjudication findings. Models can then be measured as a delta over this deterministic baseline instead of being credited for making the council exist.
