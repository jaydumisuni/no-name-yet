# Comparison Matrix

This matrix is for research and product design. It is not a dependency list.

## High-level comparison

| System | What it is good at | What we learn | What we avoid |
|---|---|---|---|
| CodeRabbit | PR-native AI review, summaries, comments, developer UX | Developers pay for fast PR review that explains issues in context | Do not depend on it; do not repeat unsafe execution/trust mistakes |
| Qodo / PR-Agent | Open-source AI PR review workflow and commands | Structured review tasks, provider abstraction, PR summary/review design | Do not become a thin wrapper around PR-Agent |
| reviewdog | Turns analyzer output into PR comments | Diagnostic normalization and line-level reporting | Do not post noisy analyzer spam |
| Semgrep | Semantic static analysis and security rules | Rules as evidence; fast local/static checks | Do not treat static findings as complete project judgment |
| CodeQL | Deep security analysis | Query-based vulnerability detection and SARIF evidence | Do not require heavy analysis for every small PR by default |
| Sider-style tools | Multi-language static analyzer orchestration | Simple setup and immediate PR feedback | Do not limit the reviewer to style/lint issues |
| Human reviewer | Context, intent, taste, judgment | Final decision must understand project direction | Do not make review depend entirely on one human being |

## What our reviewer must do better

### 1. Repository-level context

Generic reviewers often focus on the diff. Our reviewer must also understand:

- existing architecture
- project boundaries
- dependency direction
- documentation truth
- known risk areas
- long-term roadmap
- previous review lessons

### 2. Public/private safety

For THETECHGUY/Hunter projects, this is critical.

The reviewer must detect:

- private architecture leaking into public repos
- secrets or credentials
- dangerous device-recovery details exposed publicly
- internal-only naming placed in public docs
- code that suggests bypassing approval gates

### 3. Verdict over comments

Many review tools produce comments. Our reviewer must produce a decision.

The final output is:

```text
PASS
NEEDS WORK
BLOCK
```

Comments are supporting evidence. The verdict is the product.

### 4. Low-noise comments

A useful reviewer should not comment on every minor issue.

Priority levels:

```text
BLOCKER   unsafe, exploitable, private leak, broken core behavior
MAJOR     likely bug, missing test, architecture mismatch
MINOR     cleanup, style, naming, small doc issue
NOTE      optional observation
```

Only BLOCKER and MAJOR should normally affect merge readiness.

### 5. Evidence-based reasoning

Every finding should say:

- what changed
- why it matters
- what risk it creates
- what proof supports it
- what must happen before approval

### 6. No automatic edits in reviewer mode

This reviewer is not Code Ops.

It can say:

> Not enough. Try again.

It can recommend what must be fixed.

But editing belongs to Code Ops or a separate patch workflow.

## Review provider idea

Instead of depending on third-party reviewers, the system can learn from categories of evidence:

```text
Diff parser
Repository scanner
Static analyzer output
Security scanner output
Test status
Documentation checker
Architecture rules
Project memory
Owner standards
AI reasoning
```

External tools are optional evidence providers. They are not the reviewer.

## Review quality target

A strong review should answer:

1. Does the change solve the stated problem?
2. Does it break anything obvious?
3. Does it fit the architecture?
4. Are tests adequate?
5. Is the documentation still true?
6. Is it safe to expose publicly?
7. Is it maintainable?
8. Would we still accept this six months from now?
9. Is this ready to merge?

## Final positioning

The reviewer is not “our CodeRabbit.”

It should become:

> The THETECHGUY engineering standard for whether work is ready.