# Security Model

The reviewer must be secure by design because code review automation touches untrusted pull requests, repository data, CI status, GitHub APIs, and sometimes organization secrets.

The CodeRabbit/PwnedRabbit incident is the starting warning: a reviewer can become a serious supply-chain risk if analysis, execution, and credentials are mixed together.

## Security principle

```text
Reviewer logic may inspect untrusted code.
Reviewer logic must not trust untrusted code.
```

## Trust zones

### Zone 1: GitHub API collector

Purpose:

- Read repository metadata.
- Read pull request diff.
- Read changed files.
- Read CI status.

Permissions:

- read-only whenever possible
- no write token
- no repository secrets

### Zone 2: Static analysis sandbox

Purpose:

- Run safe analyzers when allowed.
- Parse code.
- Produce normalized findings.

Restrictions:

- no write token
- no long-lived secrets
- no production credentials
- strict timeout
- disposable workspace
- minimal network access
- isolated filesystem

### Zone 3: Reasoning layer

Purpose:

- Combine findings.
- Apply project rules.
- Produce verdict.

Restrictions:

- does not execute repository code
- does not call privileged GitHub write APIs
- does not load PR-controlled instructions as system policy

### Zone 4: Comment poster

Purpose:

- Post final report or review comment.

Permissions:

- limited write access for comments only
- no code execution
- no analysis tools

## Forbidden design

Never do this:

```text
PR code/config
  -> tool execution
  -> same worker with GitHub App private key
  -> write-capable installation token
```

## Required separation

Use this instead:

```text
Collector  -> read-only
Analyzer   -> sandboxed, no secrets
Reasoner   -> no execution
Poster     -> limited comment permission
```

## PR-controlled files that require caution

- GitHub Actions workflows
- package manager scripts
- Dockerfiles
- build scripts
- linter configuration
- formatter configuration
- test runner configuration
- tool configuration
- dependency lock files
- shell scripts
- documentation that changes review instructions

## Default handling

| Input type | Default handling |
|---|---|
| Changed source file | static parse allowed |
| Changed docs | inspect as text |
| Changed tests | inspect as text; do not execute automatically |
| Changed workflow | mark high risk |
| Changed build script | mark high risk |
| Changed tool config | mark high risk |
| Detected secret | block |
| Private architecture leak | block or needs work |

## Token model

The reviewer should use separate credentials per stage:

- Collector token: read-only.
- Analyzer: no token.
- Poster token: comment-only or least possible write scope.
- Admin/service secrets: never present in analysis runtime.

## Sandbox model

When execution is unavoidable, the sandbox must be:

- ephemeral
- network restricted
- resource limited
- read-only outside workspace
- destroyed after run
- unable to access production secrets

## Policy model

Project policy must come from trusted repository configuration on the base branch, not from untrusted PR changes.

If a PR changes reviewer policy files, review those policy changes but do not apply them to the same PR.

## Public/private boundary model

For THETECHGUY/Hunter projects, the reviewer must protect:

- private Hunter architecture
- device recovery approval logic
- internal business rules
- credentials or API keys
- customer/client data
- provider tokens
- private operational endpoints

## Verdict triggers

### PASS

Allowed when:

- no blocker found
- tests/docs are sufficient for risk level
- architecture remains consistent
- no public/private leaks
- no unsafe execution concerns

### NEEDS WORK

Used when:

- missing tests
- unclear behavior
- incomplete docs
- maintainability risk
- non-critical architecture concern
- fixable inconsistency

### BLOCK

Used when:

- secret leak
- private architecture leak
- unsafe execution path
- dangerous permissions
- public code exposes internal-only process
- change violates core architecture
- evidence suggests the PR should not be merged

## Security slogan

> The reviewer can be curious, but it must not be gullible.