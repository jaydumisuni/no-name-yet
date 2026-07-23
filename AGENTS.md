# Sergeant Agent Working Memory

This file is persistent operating context for every AI, coding agent, reviewer, or future chat working in this repository. Read it before planning or changing the project.

## Hunter tenfold execution method

The **10-for-2 / tenfold method is an execution rule for the agent doing the work. It is not a Sergeant product feature, worker subsystem, training rule, or architectural requirement.**

Use it as follows:

```text
one normal lead worker
→ estimate the independently useful work lanes
→ borrow Hunter's tenfold working method
→ spread the work across more parallel specialist roles
→ cross-check the results through independent review lanes
→ reconcile them into one clean result
→ finish faster without sacrificing quality
```

### Required behaviour

1. Keep one coordinating lead responsible for scope, dependencies, final reconciliation, and the delivered answer.
2. Split a substantial task into independent fronts such as implementation, tests, security, architecture, release integrity, evidence, documentation, and regression review.
3. Apply the tenfold multiplier to the normally justified worker estimate when parallel work will genuinely reduce elapsed time. Examples: work that normally needs 1 worker may use up to 10 focused roles; 2 may use 20; 5 may use 50. The multiplier is a speed-and-efficiency principle, not a fixed worker count or a reason to invent unnecessary work.
4. Run independent fronts in parallel when their inputs and write targets do not conflict.
5. Serialize destructive operations, dependent steps, and multiple writes to the same file, branch, release, or external record.
6. Give each role a distinct question or deliverable. Do not create ten copies of the same reasoning.
7. Cross-check important conclusions with at least one independent evidence or review lane. High-risk merge, release, deletion, security, integrity, or preservation decisions require stronger proof appropriate to the risk.
8. Reconcile disagreements explicitly. The coordinating lead must remove duplication, verify claims against source evidence, and produce one consistent verdict.
9. Preserve the existing quality, safety, provenance, test, and review gates. Speed must come from parallel decomposition and clean coordination, never from skipping proof.
10. Report the consolidated result rather than flooding the user with internal worker chatter.

## Interpretation boundary

The user's exact wording is the requirement. Do not expand a workflow instruction into product architecture, model training, a Sergeant capability, or a new subsystem unless the user explicitly asks for that change.

In particular:

- "Use 10-for-2" means **work faster and efficiently through coordinated parallel roles and cross-checking**.
- It does **not** mean add another private-force implementation to Sergeant.
- It does **not** authorize extra features, models, agents, branches, workflows, or storage by itself.
- When ambiguity remains, preserve the narrow operational meaning instead of assuming a broader design change.

## Completion standard

A task is complete when the coordinated lanes have produced a source-grounded, internally consistent result; required checks have passed; risks and blockers are stated honestly; and no quality standard was dropped for speed.
