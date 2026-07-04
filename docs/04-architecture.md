# Reviewer Architecture

This is the first architecture draft for Main Review.

## Architecture goals

- Independent from CodeRabbit, Qodo, PR-Agent, or any single vendor.
- Learns from existing reviewer patterns without depending on them.
- Produces final review verdicts, not automatic patches.
- Keeps untrusted PR code away from secrets and write access.
- Supports project-specific standards and memory.
- Scales from local review to GitHub PR review.

## High-level flow

```text
Repository / Pull Request
        ↓
Collector Layer
        ↓
Context Builder
        ↓
Safety Preflight
        ↓
Evidence Providers
        ↓
Review Reasoning Layer
        ↓
Verdict Engine
        ↓
Report / PR Comment / Dashboard
```

## 1. Collector Layer

Collects information without executing project code.

Inputs:

- repository metadata
- changed files
- diff hunks
- commit messages
- PR title/body
- issue links
- existing docs
- test files
- dependency manifests
- CI status

Rules:

- read-only access only
- no write token
- no repo scripts
- no package install
- no project test execution at this stage

## 2. Context Builder

Builds a repository understanding packet.

Outputs:

- project type
- language/frameworks
- architecture map
- important modules
- public/private boundaries
- known risk files
- test strategy
- documentation map
- dependency map

Context should be cached and updated incrementally.

## 3. Safety Preflight

Before any deeper analysis, decide what is safe to inspect.

Checks:

- changed workflow files
- changed build scripts
- changed linter configs
- changed package install scripts
- changed Dockerfiles
- changed review/tool configuration
- sensitive values or credentials
- public/private leakage

Possible outputs:

```text
SAFE_FOR_STATIC_ANALYSIS
STATIC_ONLY
SANDBOX_REQUIRED
BLOCK_TOOL_EXECUTION
BLOCK_REVIEW
```

## 4. Evidence Providers

Evidence providers create facts. They do not make final decisions.

Potential providers:

- diff parser
- static analyzer
- dependency scanner
- secret scanner
- test detector
- documentation checker
- architecture rule checker
- public safety checker
- Semgrep provider
- CodeQL provider
- reviewdog-style diagnostic importer
- AI code reasoning provider

Provider output should be normalized:

```json
{
  "provider": "example",
  "severity": "major",
  "file": "path/to/file",
  "line": 42,
  "category": "security",
  "message": "Finding summary",
  "evidence": "Why this finding exists",
  "confidence": "medium"
}
```

## 5. Review Reasoning Layer

This layer asks the real engineering questions.

Examples:

- Does this solve the stated problem?
- Does it duplicate existing code?
- Does it violate architecture boundaries?
- Does it need tests?
- Does it expose private Hunter logic?
- Does it break the product story?
- Is this maintainable?
- Is the documentation still true?

This layer combines:

- evidence provider findings
- repo context
- project rules
- Code Ops standards
- review memory
- owner principles

## 6. Verdict Engine

The verdict engine converts review reasoning into a decision.

Verdicts:

```text
PASS
NEEDS WORK
BLOCK
```

Rules:

- Any confirmed secret leak => BLOCK.
- Any unsafe execution path => BLOCK.
- Any public/private boundary leak => BLOCK or NEEDS WORK depending on severity.
- Missing tests for critical behavior => NEEDS WORK.
- Documentation contradiction for user-facing behavior => NEEDS WORK.
- Style-only issues should not block unless they indicate deeper inconsistency.

## 7. Report Layer

The report must be useful and short enough to act on.

Report sections:

```text
Verdict
Reason
Blocking findings
Major findings
Minor findings
Tests/docs status
Security/public safety status
Suggested next action
```

## GitHub PR mode

The reviewer should run in two separated phases:

```text
Read-only analysis worker
        ↓
Report artifact
        ↓
Limited-permission comment poster
```

The analysis worker must not have write access.

The comment poster must not execute code.

## Local mode

Local mode can be used before PRs:

```bash
main-review scan
main-review review --base main --head feature-branch
main-review report
```

Local mode should still avoid blindly executing project scripts.

## Future dashboard mode

A dashboard can show:

- review history
- repeated issue patterns
- repo risk score
- reviewer confidence
- project quality trend
- unresolved architecture warnings

## Architecture principle

The reviewer should be modular enough to improve over time without changing its identity.

```text
Providers can change.
Models can change.
Rules can change.
The verdict standard remains.
```