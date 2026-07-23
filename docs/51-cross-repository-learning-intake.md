# Sergeant cross-repository learning intake

## Purpose

Sergeant must strengthen itself from useful engineering evidence wherever that evidence is produced. A signal does not need to originate in the Sergeant repository. THETECHGUY projects, external open-source repositories, GitHub Actions, review tools, runtime failures, repair commits, and test regressions may all contribute.

The boundary is usefulness and proof—not repository ownership.

## Intake sequence

```text
repository event
→ sanitized signal inbox
→ tenfold officer/private triage
→ evidence-only / needs-lineage / candidate-ready / rejected
→ frozen blind Sergeant review
→ fixing truth reveal
→ Teacher / Prosecutor / Defender
→ negative controls
→ unrelated-language or unrelated-repository transfer
→ hidden holdout
→ owner-controlled proposal
```

No signal, candidate, worker packet, or proposal has automatic promotion or merge authority.

## Signal classes

### Candidate-ready

A signal can enter the governed learning queue only when it has:

- exact repository and source URL;
- a distinct full defective commit and fixing commit;
- a source PR or direct source-event URL;
- production paths and language;
- evidence proving the defect;
- evidence verifying the repair;
- a blind review that can be frozen before truth reveal;
- no credential-like material.

### Needs lineage

Useful investigation material is retained when it may expose a defect but still lacks a complete before/after chain. Examples include:

- a shell trace around suspicious code;
- a workflow failure without a verified fixing commit;
- a CodeRabbit or Sergeant finding that has not yet become a regression;
- a runtime log without exact source binding.

The signal is not discarded. Officers and tenfold private cells may recover the missing provenance.

### Evidence-only

Some repository activity is worth preserving but should not teach defect detection. Examples include:

- formatting-only commits;
- style or documentation changes;
- a successful build with no defect/fix claim;
- a one-shot automation commit that changes presentation but not behavior.

These records may still teach operational patterns, release mechanics, or evidence handling, but they cannot become a permanent behavioral lesson without a separate verified defect lineage.

### Rejected

Signals are rejected when they are malformed, lack a repository/source identity, contain credential-like material, or have no usable engineering context.

## Current THETECHGUY examples

### TechGuyCheckm8 formatting commit

Commit `064700fadc54b997b61d6d5d1c31ed13b844c673` removes a one-shot formatting workflow and applies `rustfmt` layout changes. It contains no functional defect/fix evidence. Its correct disposition is **evidence-only**, not a code-review lesson.

The self-removing one-shot workflow may still be studied as an operational automation pattern.

### Lumi background investigation

A shell trace locating and inspecting `browser-extension/background-v5.js` is a useful **needs-lineage** signal. It becomes candidate-ready only after it is bound to:

- the exact failing behavior;
- the defective commit;
- the fixing commit;
- relevant source paths;
- proof or tests showing the repair.

Lumi pull requests, accepted review findings, runtime failures, and permanent regressions are valid Sergeant training sources when those requirements are satisfied.

### Lumi token-origin benchmark

The real-code benchmark in Sergeant PR `#143` is now a **candidate-ready** learning signal, not an accepted lesson.

Pinned lineage:

```text
repository: jaydumisuni/lumi-dm
pre-fix: 8f63f832112a2e0772e954c3e0319109ce21b6a9
fix: a8d572258a4d53e9620970e5236ab21aa903580f
file: browser-extension/security-shim.js
```

The pre-fix extension attached its bearer credential to any loopback-host `/api/` destination. The repair binds credential attachment to the exact configured Lumi server origin. Current model-free Sergeant returned the same generic missing-tests finding for both code states, so the benchmark froze two learning objectives:

1. learn the generalized credential-destination boundary across host, port, scheme, subdomain, IPv4/IPv6 loopback, redirects, malformed configuration, request-object forms, and existing credential headers;
2. improve clean-control discrimination so a vulnerable snapshot and its repaired control do not receive an identical unrelated finding.

The source record is `.github/self-learning/signals/lumi-token-origin-2026-07-23.json`. It may enter Teacher, Prosecutor, and Defender work, but it cannot become a permanent officer or detector until executable positive cases, clean controls, unrelated transfer, and hidden holdout pass.

## Tenfold triage

Every retained cross-repository signal receives a human-equivalent workload estimate. Sergeant applies the existing private-force law through `private_force_size`:

```text
2 workers  → 20 privates
5 workers  → 50 privates
12 workers → 120 privates
```

Private lanes must have distinct evidence obligations. They may recover provenance, reproduce failures, inspect architecture, verify tests, challenge security assumptions, or search for clean counterexamples. They cannot issue the final verdict or promote a lesson.

## Storage and privacy

- Raw credentials, authorization headers, cookies, tokens, passwords, and private local paths are never accepted into the signal packet.
- Large logs and screenshots remain in approved durable evidence storage; the queue records bounded references and digests.
- Rejected and evidence-only signals are retained when they have future diagnostic value.
- External repository licences and access rules remain binding.

## Source registry

`.github/self-learning/cross-repository-sources.json` records confirmed source repositories and their known language/evidence boundaries. The registry begins with `jaydumisuni/TechGuyCheckm8` and `jaydumisuni/lumi-dm`, while the existing public multilingual pool remains available for unrelated transfer and holdout work.

The registry is expandable. It is not a whitelist that prevents another useful repository from contributing; it is the set whose access and provenance policy has already been confirmed.
