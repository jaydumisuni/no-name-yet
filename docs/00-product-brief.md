# Product Brief

## Working identity

Temporary repository name: `no-name-yet`.

Temporary product label: **Main Review**.

The final name should be decided later. The important part is the role:

> The final engineering reviewer that decides whether a change is good enough to move forward.

## Problem

Modern AI coding tools can generate code quickly, but fast code creates a new problem: review quality becomes the bottleneck.

Generic AI reviewers help, but they usually lack the full project context:

- long-term architecture
- private/public boundaries
- owner standards
- project history
- lessons from previous mistakes
- business direction
- release expectations

A good reviewer should not only ask whether the code compiles. It should ask whether the change belongs in the project.

## Product goal

Create an independent reviewer that studies best-in-class tools, learns from their strengths and failures, and applies THETECHGUY/Hunter engineering standards as the final decision layer.

This reviewer should stand on its own. External reviewers can be studied or benchmarked, but they must not become dependencies.

## Non-goals

This reviewer does not begin as a patching system.

It should not:

- rewrite code automatically
- push fixes by itself
- run untrusted PR code in a privileged environment
- hold write tokens while reviewing
- copy CodeRabbit/Qodo branding or code
- depend on one commercial platform

## Primary outcomes

Every review should end with one verdict:

```text
PASS        The change is acceptable.
NEEDS WORK  The change is not ready, but the issue is fixable.
BLOCK       The change is unsafe, misleading, or architecturally wrong.
```

## Product personality

The reviewer should be calm, direct, and strict.

It should not flood the developer with noise. It should explain what matters, why it matters, and what must change before approval.

Its attitude is:

> Not enough. Try again.

or:

> This clears the standard.

## Why this can be stronger than generic reviewers

This reviewer is designed to combine:

- repo-level understanding
- static analysis evidence
- AI reasoning
- project memory
- Code Ops standards
- security boundaries
- owner philosophy
- external research lessons

The final advantage is not one model or one tool. The advantage is a better review process.
