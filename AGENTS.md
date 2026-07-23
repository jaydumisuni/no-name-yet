# Sergeant Agent Working Memory

This file is persistent operating context for every AI, coding agent, reviewer, or future chat working in this repository. Read it before planning or changing the project.

## The two valid meanings of 10-for-2

The phrase **10-for-2 / Hunter's tenfold method has two distinct, valid meanings. Context decides which one applies. Do not erase either meaning and do not merge them into one vague rule.**

### 1. Assistant execution method

When the user asks a chat, coding agent, or AI worker to use 10-for-2, the agent should work faster through coordinated parallel decomposition:

```text
one coordinating lead
→ estimate the independently useful work lanes
→ split the work across parallel specialist roles
→ cross-check important conclusions through independent lanes
→ reconcile conflicts and duplication
→ return one clean result faster without sacrificing quality
```

Required behaviour:

1. Keep one coordinating lead responsible for scope, dependencies, final reconciliation, and the delivered answer.
2. Split substantial work into independent fronts such as implementation, tests, security, architecture, release integrity, evidence, documentation, and regression review.
3. Run safe independent fronts in parallel when their inputs and write targets do not conflict.
4. Serialize destructive operations, dependent steps, and multiple writes to the same file, branch, release, or external record.
5. Give each role a distinct question or deliverable; do not create copies of the same reasoning.
6. Cross-check high-risk merge, release, deletion, security, integrity, and preservation decisions with independent evidence appropriate to the risk.
7. Preserve all existing quality, safety, provenance, test, and review gates. Speed comes from decomposition and coordination, never from skipping proof.
8. Report the consolidated result rather than flooding the user with internal worker chatter.

### 2. Sergeant internal force doctrine

Inside Sergeant's own architecture, 10-for-2 is also the machine-scale officer/private-force rule that enables faster code review and learning.

```text
normally justified human-equivalent workers × 10
2 workers → 20 privates
5 workers → 50 privates
12 workers → 120 privates
```

This doctrine means:

- Sergeant remains the final proof, admission, and engineering authority.
- Cpl is the reasoning council itself: model reasoning when enabled, live online/repository lookup, evidence comparison, mission decomposition, and force coordination.
- Officers define distinct specialist perspectives and evidence duties.
- Privates form parallel investigative cells that gather, test, challenge, and cross-check evidence.
- Hermes transports orders and evidence; Hermes does not command the operation.
- The private count is a machine-work multiplier, not a count of paid model calls. A cell may combine deterministic workers, scanners, memory retrieval, local models, and bounded external specialists.
- Twenty is the minimum machine-scale formation for work that would normally justify two workers; it is not the ceiling.
- The force must scale only when additional independent lanes genuinely improve elapsed time, coverage, or falsification strength.

Do not remove this internal doctrine merely because the same phrase is also used as an assistant execution instruction.

## External repository activity is candidate learning evidence

Useful fixes, reviews, failures, workflow corrections, and implementation improvements from repositories outside `jaydumisuni/Sergeant` may strengthen Sergeant. They are not excluded because they happened in another repository.

Examples include THETECHGUY repositories such as TechGuyCheckm8, lumi-dm, Hunter, TechGuy Tool, and other owned projects, as well as suitable public repositories.

External activity does **not** become knowledge automatically. It enters a controlled learning lane:

```text
capture defective or pre-fix state
→ pin repository, commit, files, language, and provenance
→ freeze Sergeant's blind review before revealing the fix
→ reveal and verify the fixing change
→ derive a generalized candidate lesson
→ Teacher proposes
→ Prosecutor strengthens and challenges
→ Defender builds negative controls and tries to destroy overfitting
→ test unrelated repositories or languages where appropriate
→ run hidden holdout
→ admit only proven transferable value into Sergeant-owned rules, tests, benchmarks, tools, or memory
```

Required boundaries:

1. A GitHub notification, pushed commit, successful script, or green workflow is only a discovery signal.
2. Formatting-only, dependency-noise, generated-file, or repository-specific changes may be rejected as non-learning material.
3. Preserve exact source lineage and distinguish formatting, repair, feature work, and true defect correction.
4. Freeze blind-before-learning evidence so Sergeant cannot receive the answer before its review.
5. Keep accepted lessons model-free where practical by converting them into Sergeant-owned detectors, tests, benchmarks, proof rules, and durable memory.
6. Retain rejected lessons and reasons; rejection is valuable false-positive control evidence.
7. Never copy external code or conclusions as authority merely because another model, reviewer, bot, or repository produced them.

See `docs/EXTERNAL_REPOSITORY_LEARNING_POLICY.md` for the intake record and admission boundary.

## Interpretation boundary

The user's exact wording and current context define which meaning is active:

- A request about how a chat or AI should execute work invokes the **assistant execution method**.
- A request about Sergeant's officers, privates, review force, learning speed, or internal operation invokes the **Sergeant force doctrine**.
- A request may intentionally invoke both.
- Useful work from other repositories may be offered as **candidate Sergeant training evidence**, but it still requires controlled verification before admission.

Do not collapse a dual-context instruction into only one meaning again.

## Completion standard

A task is complete when coordinated lanes have produced a source-grounded, internally consistent result; required checks have passed; risks and blockers are stated honestly; useful external evidence has been classified correctly; and no quality standard was dropped for speed.