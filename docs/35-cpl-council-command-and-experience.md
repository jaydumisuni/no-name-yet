# Cpl Council Command and Verified Experience

## Status

Implemented on top of the permanent-officer amplification baseline.

Cpl is Sergeant's senior field-reasoning officer. It is not one model, a gateway name, or a replacement for the permanent squad.

## Command relationship

```text
Sergeant / Commander
        ↓
Cpl — council-led field command
        ↓
Permanent officers
        ↓
Armoury weapons, model support members, tests, and scanners
        ↓
Judge-qualified outcomes
        ↓
Archivist-governed experience
```

- Sergeant owns the final engineering verdict and deterministic gates.
- Cpl forms and chairs the model council, tables issues, deploys support, improves instructions, and reports mission state.
- Permanent officers retain universal training, specialist doctrine, evidence duties, experience, and their own reports.
- Models are replaceable council members and officer-support engines.
- The Armoury supplies proof capabilities.
- Human or Judge-confirmed outcomes are required before durable learning.

## Elastic council

Cpl starts with the models already justified by the mission and existing specialist plan. It recruits another model only when it can name a gap such as:

- a planned officer report failed;
- council verdicts disagree;
- an unanswered evidence question remains;
- a blocker or major finding has only one model source;
- verified memory indicates a possible recurrence.

Council growth is bounded:

```text
SERGEANT_CPL_MAX_ROUNDS=1..6
SERGEANT_CPL_MAX_COUNCIL_MEMBERS=1..12
```

Depth defaults remain:

- `single` — one general member and no follow-up council round;
- `adaptive` — smallest sufficient council;
- `deep` — deeper specialist coverage and additional rebrief capacity;
- `maximum` — every current specialist with the largest bounded council.

More models are not treated as votes. Repository evidence, deterministic proof, officer relevance, model independence, unanswered objections, and recurrence history remain visible.

## Council loop

```text
1. Cpl retrieves relevant verified and rejected experience.
2. Core council members and permanent-officer support bots inspect current evidence.
3. Cpl tables their reports.
4. Cpl detects a named gap.
5. Cpl recruits or reuses the smallest suitable model member.
6. Cpl sends a focused rebrief to the responsible permanent officer.
7. The officer-supported model returns grounded evidence or preserves uncertainty.
8. Cpl records whether the gap was answered.
9. The loop repeats within strict round and member limits.
10. Cpl returns findings, remaining gaps, recurrence state, council history, and confidence to Sergeant.
```

A later council report can close a tracked gap only by answering the exact tabled issue. Old disagreement or failed-attempt records are preserved in the audit trail but do not remain falsely open after a grounded follow-up resolves them.

## Experience system

The canonical engineering lesson store remains:

```text
.main-review/memory.json
```

Operational experience is append-only:

```text
.main-review/cpl-experience.jsonl
```

The ledger records verified, rejected, or superseded outcomes for:

- Cpl command decisions;
- permanent officers;
- model council members;
- Armoury weapons.

Profiles are derived from ledger events rather than silently mutated. A model can be replaced while Engineer, Medic, Mechanic, or another officer retains verified specialist experience.

Raw model findings are never written directly to durable experience. The learning path is:

```text
Review finding
→ explicit human/Judge outcome
→ canonical lesson candidate
→ verified/rejected memory record
→ Cpl/officer/model/weapon experience event
→ future retrieval
```

## Anti-repeat behavior

The system does not promise that code can never reintroduce the same defect. It enforces the stronger realistic rule:

> Applicable verified experience must influence the next mission, or Cpl must preserve why it could not be reused.

When a current grounded finding resembles a verified prior incident, Cpl tables recurrence as a council gap. The responsible officer must investigate why the earlier prevention failed and require stronger regression proof.

## Officer behavior

Officers are not brainless order carriers. Each officer receives:

- shared Cpl field intelligence;
- current council state;
- targeted model support reports;
- relevant verified and rejected officer experience;
- Cpl rebrief instructions;
- recurrence obligations where applicable.

An officer can complete the assignment, preserve uncertainty, or return evidence that the instruction needs correction. Cpl then rebriefs the council and the next responsible officer.

## Output contract

`cpl_review` now includes:

```text
memory_checked
experience
recurrences
council.mode
council.rounds
council.members
council.recruitment
council.agreement
council.model_independence
council.final_gaps
council.complete
council.officer_instructions
```

The existing `semantic_review` alias remains for Sergeant 0.4.0 integrations.

## Safety

- Read-only review remains the default.
- No council member receives repository write or merge authority.
- Remote endpoints are never auto-discovered.
- Credentials remain environment-only.
- Unsupported blocker or major findings are rejected by the existing grounding boundary.
- Current repository and runtime evidence outrank stale memory.
- Sergeant remains the final authority.

## Definition of done

Cpl is complete for this phase when:

- the three-stripe interface identity is restored and package-locked;
- multiple models can serve as distinct council members;
- one model degrades honestly into role-separated passes;
- named gaps trigger bounded follow-up rounds;
- permanent officers receive support, instructions, and experience;
- recurrence creates an actionable prevention review;
- only verified outcomes update durable experience;
- reports expose council history and unresolved gaps;
- existing reviewer, CLI, App Bridge, IDE, packaging, clean-clone, battle, and Command Center proof remain green.
