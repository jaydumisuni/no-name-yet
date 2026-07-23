# Sergeant Agent Working Memory

This file is persistent operating context for every AI, coding agent, reviewer, or future chat working in this repository. Read it before planning or changing the project.

## Hunter tenfold / 10-for-2 doctrine

The **10-for-2 / tenfold method has two linked applications**:

1. it governs how any AI, chat, coding agent, or reviewer should execute substantial work on Sergeant; and
2. it is a core Sergeant operating law used by Cpl, permanent officers, and private cells for fast code review and governed learning.

Do not separate these meanings. Sergeant depends on the same disciplined parallelism that working agents should use.

## Sergeant command chain

```text
Owner
→ Sergeant
→ Cpl council
→ permanent officers
→ task workers / privates
→ models, tools, scanners, and workspace capabilities
```

Hermes carries orders, evidence, status, and provenance across every level. Hermes does not command, promote lessons, or issue Sergeant's final verdict.

## Sergeant private-force law

Sergeant estimates the normally justified human-equivalent worker requirement and deploys ten times that number as privates:

```text
2 human-equivalent workers  → 20 privates
5 human-equivalent workers  → 50 privates
12 human-equivalent workers → 120 privates
```

Twenty privates is the minimum machine-scale formation for work equivalent to two ordinary workers. It is not a ceiling. Larger missions scale proportionally, and a mission may contain multiple bounded private cells.

Permanent officers own specialist doctrine and split code review or learning work into distinct evidence obligations. Privates investigate those obligations in parallel through deterministic checks, models, tools, scanners, repository evidence, or approved workspace capabilities. The responsible officer cross-checks and reconciles the evidence before it moves upward. Sergeant remains final authority.

This tenfold private-force system is one of the mechanisms that gives Sergeant rapid code review and rapid learning without sacrificing proof.

## Cross-repository learning memory

Sergeant must consider **all useful THETECHGUY and external repository signals**, not only activity inside the Sergeant repository. Commits, pull requests, workflow runs, review findings, runtime logs, shell traces, test failures, repairs, and release failures may contribute evidence.

Every signal is governed before it can teach Sergeant:

```text
repository event
→ sanitized signal intake
→ tenfold officer/private triage
→ evidence_only / needs_lineage / candidate_ready / rejected
→ frozen blind review
→ fixing truth reveal
→ Teacher / Prosecutor / Defender
→ negative controls
→ unrelated-language or unrelated-repository transfer
→ hidden holdout
→ owner-controlled promotion proposal
```

A bot commit, formatting change, shell transcript, successful build, or review comment is **not automatically a lesson**. It may be retained as evidence or sent for lineage recovery. A candidate needs exact repository and event provenance, a confirmed defective state, a verified fixing state, scored production paths, evidence references, and a blind-review boundary. No signal, candidate, or proposal has automatic promotion or merge authority.

`.github/self-learning/cross-repository-sources.json` records sources whose access and evidence boundaries are already confirmed. It is not an exclusion list: another useful repository remains eligible when its provenance and access can be verified.

## Working-agent tenfold method

Any AI or chat working on Sergeant should mirror the same discipline:

```text
one coordinating lead
→ estimate the independently useful work lanes
→ expand the normally justified worker estimate through Hunter's tenfold method
→ assign distinct parallel specialist roles
→ cross-check results through independent evidence or review lanes
→ reconcile disagreements into one clean result
→ finish faster without sacrificing quality
```

### Required behaviour

1. Keep one coordinating lead responsible for scope, dependencies, final reconciliation, and the delivered answer.
2. Split substantial work into independent fronts such as implementation, tests, security, architecture, release integrity, evidence, documentation, and regression review.
3. Apply the tenfold multiplier when parallel work genuinely reduces elapsed time: two normally justified workers map to twenty roles, five to fifty, and twelve to one hundred twenty. Do not treat twenty as a ceiling.
4. Run independent fronts in parallel when their inputs and write targets do not conflict.
5. Serialize destructive operations, dependent steps, and multiple writes to the same file, branch, release, or external record.
6. Give each role a distinct question or deliverable. Do not create duplicate noise.
7. Cross-check important conclusions with independent evidence. High-risk merge, release, deletion, security, integrity, preservation, lesson-promotion, or final-verdict decisions require proof appropriate to the risk.
8. Reconcile disagreements explicitly. The coordinating lead must remove duplication, verify claims against source evidence, and produce one consistent verdict.
9. Preserve existing quality, safety, provenance, test, learning, and review gates. Speed comes from parallel decomposition and clean coordination, never from skipping proof.
10. Report the consolidated result rather than flooding the user with internal worker chatter.

## Interpretation boundary

The user's exact wording is the requirement. Do not erase an existing Sergeant mechanism merely because the same phrase is also a working instruction.

In particular:

- "Use 10-for-2" means work faster through coordinated tenfold parallel roles and cross-checking.
- Inside Sergeant, the same rule is already the private-force scaling law used by officers and privates for review and learning.
- It does not authorize uncontrolled scope growth, duplicate roles, automatic lesson promotion, automatic merge, or weaker evidence gates.
- It does not require inventing a second tenfold subsystem; preserve and use Sergeant's existing private-force implementation correctly.

## Completion standard

A task is complete when the coordinated lanes have produced a source-grounded, internally consistent result; required checks have passed; officers or working agents have reconciled contradictions; useful cross-repository signals have been retained, qualified, or rejected with evidence; risks and blockers are stated honestly; and no quality standard was dropped for speed.
