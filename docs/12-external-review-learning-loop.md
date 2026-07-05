# External Review Learning Loop

This workflow captures how Main Review can learn from external reviewers without depending on them.

The goal is not to make CodeRabbit, Qodo, PR-Agent, or any other reviewer happy.

The goal is to consume their reviews, classify each useful signal, fix what is truly correct, reject what conflicts with our architecture, and save reusable patterns so Main Review learns to detect them itself.

## Source principle

> External reviewers are training material, not final authority.

## Review comment classification

Every external review comment should be classified as one of four outcomes:

```text
🟢 Correct
🟡 Good suggestion
🔴 Reject
🧠 Save the pattern
```

### 🟢 Correct — fix immediately

Use this when the comment identifies a real bug, unsafe behavior, broken test, inaccurate docs, bad contract, or maintainability issue that clearly applies.

Action:

- fix the issue
- reference the finding in the PR notes
- consider whether the pattern should become a Main Review evidence rule

### 🟡 Good suggestion — consider if it fits

Use this when the comment has value but needs owner/project judgment.

Action:

- compare with architecture
- check if it matches product direction
- accept only if it improves the project without unnecessary complexity

### 🔴 Reject — does not fit

Use this when the comment is stylistic noise, generic advice, or conflicts with intentional design.

Action:

- document why it is rejected
- do not bend the project just to satisfy an external reviewer
- optionally save the rejection as a memory lesson so the future reviewer avoids the same bad suggestion

### 🧠 Save the pattern — teach Main Review

Use this when the comment reveals a reusable review pattern.

Action:

- convert the pattern into a memory record, rule, or future evidence-provider idea
- capture where it came from
- describe why it matters

## Workflow for the three hackathon repos

For each repo:

```text
1. Collect external reviewer comments.
2. Classify every comment.
3. Fix 🟢 items.
4. Evaluate 🟡 items against our architecture.
5. Reject 🔴 items with reasons.
6. Save 🧠 patterns into Review Memory.
7. Repeat until only accepted/rejected/learned items remain.
```

The three repos are:

- `hunter-foreman`
- `hunter-foreman-demo`
- `hunter-foreman-docs`

## Why this matters

External reviewers have already reviewed many changes across earlier work.

That is valuable training material. Losing it would waste real review history.

Each surviving comment teaches Main Review what a useful reviewer should notice:

- missing tests
- unsafe assumptions
- unclear docs
- API contract mismatch
- architecture drift
- config risk
- CI risk
- maintainability debt
- confusing developer experience

## Memory conversion format

When a pattern is worth saving, convert it into Review Memory.

Example:

```bash
main-review memory add \
  --kind lesson \
  --title "External reviewer caught missing receiver validation" \
  --summary "Bridge contract changes require receiver-side validation tests." \
  --reason "A sender-only test can pass while the receiving app still accepts malformed payloads." \
  --status verified \
  --tag external-review \
  --tag contract \
  --tag testing \
  --applies-to api-contracts \
  --confidence 0.9
```

## Main Review future behavior

Eventually Main Review should reproduce the useful parts of this workflow automatically:

```text
PR arrives
  ↓
Main Review scans external-style patterns internally
  ↓
Findings are classified by architecture fit
  ↓
Verdict is produced
  ↓
Useful new lessons are proposed for memory
```

## Important distinction

We are not training Main Review to imitate CodeRabbit.

We are teaching it to outperform external reviewers by combining:

- external review patterns
- Code Ops standards
- repository intelligence
- review memory
- Jay's engineering philosophy
- evidence-based verdicts

## Guiding sentence

> Every external review comment that survives scrutiny becomes training material for our reviewer.
