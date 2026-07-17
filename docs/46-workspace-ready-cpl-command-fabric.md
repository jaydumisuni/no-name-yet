# Workspace-ready Cpl command fabric

Sergeant now defines the operational contracts required to connect Ptah or
another Hunter Workspace later without redesigning Cpl, the permanent
officers, private cells, Hermes, or Sergeant's final authority.

## What is implemented now

- versioned Sergeant mission packets;
- Cpl campaign and council-round state;
- permanent-officer task ownership;
- the 10× private-force rule, with twenty as the minimum formation;
- hypotheses, falsifiers, dependencies, stop conditions, and escalation rules;
- bounded workspace and live-research requests;
- strict evidence packets that cannot issue verdicts or escape scope;
- pending authorization for newly discovered questions;
- replayable Hermes transactions and provenance requirements;
- replaceable workspace and research adapter protocols;
- adapter capability checks before any execution;
- rejection of adapter output that attempts to create command authority;
- required source, time, freshness, and supported-claim provenance for live research;
- model support recorded beneath permanent officers.

## What is intentionally not claimed

No terminal, browser, device, sandbox, or general-web facility is represented
as connected merely because these contracts exist. Until a real adapter is
supplied, authorized requests remain `awaiting_adapter` or
`awaiting_capability` and produce no evidence. Existing deterministic review
remains usable and authoritative.

## Connection model

```text
Sergeant mission and proof boundary
    -> Cpl campaign and council round
    -> permanent officer task authorization
    -> 10× private-cell execution plan
    -> Ptah/Hunter Workspace or governed research adapter
    -> validated private evidence packet
    -> responsible officer
    -> Analyst / Challenger / Judge
    -> Cpl complete ground report
    -> Sergeant verdict
```

Models and facilities are capabilities, not ranks. A model can strengthen an
Engineer, Medic, Mechanic, Scout, Challenger, or Judge-support assignment, but
cannot become that officer or issue Sergeant's verdict. Workspace facilities
can execute approved tasks, but cannot create authority, expand scope, or
promote their own output into memory.

## Future Ptah adapter expectations

A Ptah adapter should implement the existing workspace interface and report:

- capability inventory and facility identity;
- exact environment and source revision;
- execution status, logs, tests, traces, screenshots, recordings, or artifacts;
- evidence and artifact provenance;
- incomplete or failed task state;
- privacy and permission enforcement;
- no final verdict.

Sergeant checks the adapter's declared capabilities before dispatch, verifies
that request scope remains inside the authorized officer task, and rejects any
result containing mission, task-authorization, or verdict fields.

A governed research adapter should accept only bounded questions, apply source
and domain policy, remove private context, cache results, preserve retrieval
time and source provenance, disclose conflicts, and return evidence to Scout
and the responsible officer rather than directly controlling the gate.
Research evidence is not accepted without the adapter identity, observation
and retrieval times, source, freshness, and the exact supported claim.
