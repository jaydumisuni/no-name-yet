# Sergeant tenfold operating doctrine

## Dual meaning

Hunter's **10-for-2 / tenfold method** is both:

1. a working method for any AI, chat, coding agent, or reviewer operating on Sergeant; and
2. a core Sergeant execution law used by Cpl, permanent officers, and private cells during code review and governed learning.

These meanings reinforce each other. The working agent should use the same disciplined parallelism that Sergeant uses internally.

## Sergeant command chain

```text
Owner
→ Sergeant
→ Cpl council
→ permanent officers
→ task workers / privates
→ models, tools, scanners, and workspace capabilities
```

Hermes carries orders, evidence, status, and provenance across the chain. Hermes does not command, promote lessons, or issue the final verdict.

## Private-force law

Sergeant estimates the normally justified human-equivalent worker requirement, then deploys a private force at ten times that estimate:

```text
2 human-equivalent workers  → 20 privates
5 human-equivalent workers  → 50 privates
12 human-equivalent workers → 120 privates
```

Twenty privates is the minimum machine-scale formation for work equivalent to two ordinary workers. It is not the mission ceiling.

Permanent officers split review or learning work into bounded evidence obligations. Privates investigate those obligations in parallel through distinct roles, tools, scanners, models, or deterministic checks. The responsible officer cross-checks and reconciles the evidence before it moves upward. Sergeant remains final authority.

## Why Sergeant depends on it

The tenfold method is what gives Sergeant rapid code review and rapid governed learning without replacing proof with speed:

- more independent investigation lanes can run at once;
- officers can compare findings rather than trusting one path;
- false positives and contradictions are exposed earlier;
- language, architecture, security, tests, lifecycle, concurrency, and regression risk can be covered in parallel;
- learning candidates can be challenged by Teacher, Prosecutor, Defender, negative controls, transfer tests, and holdouts without serial bottlenecks.

The multiplier never authorizes duplicate noise, uncontrolled scope growth, automatic lesson promotion, or weaker evidence gates.

## Working-agent rule

Any AI or chat picking up Sergeant work should mirror this method:

```text
one coordinating lead
→ split substantial work into distinct parallel specialist lanes
→ run independent lanes safely
→ cross-check evidence
→ reconcile disagreements
→ deliver one clean result faster without sacrificing quality
```

This does not mean inventing a new tenfold subsystem. Sergeant already has the private-force mechanism. The instruction is to preserve and use it correctly, both in the product and in the way agents work on the product.
