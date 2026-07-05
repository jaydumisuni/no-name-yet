# Sergeant

Sergeant is an open-source engineering reviewer.

It can be used inside THETECHGUY/Hunter, but the public repository is not limited to THETECHGUY. The public version focuses on reusable review infrastructure:

- repository and diff inspection
- review intelligence
- evidence consensus
- verified learning
- graduation benchmarking
- squad-style specialist reports
- read-only GitHub PR comment ingestion

Sergeant is not a patch writer. It does not edit code by itself. Its job is to understand a repository, inspect a pull request or change set, compare the work against standards, and return one of three outcomes:

```text
PASS
NEEDS WORK
BLOCK
```

## Public boundary

The public repository must stay useful to other engineering teams without leaking private THETECHGUY/Hunter rules or operational details.

Public:

- review engine
- app bridge
- static analysis
- evidence consensus
- verified learning framework
- squad orchestration
- read-only GitHub comment fetch

Private/project-specific:

- THETECHGUY/Hunter private standards
- private repository memory
- customer/client evidence
- deployment secrets
- write-token GitHub bot operations

## What Sergeant refuses to do

Sergeant reviews evidence. It must not become an unsafe execution engine.

It refuses to:

- execute pull-request-controlled code
- run shell commands from PR content
- use write tokens during analysis
- silently fake success after a failed live fetch
- treat external reviewers as authorities
- write patches as part of review

## Core principle

> The reviewer must understand danger, but must not execute danger.

This comes directly from CodeRabbit/PwnedRabbit security lessons: reviewer systems become dangerous when they execute untrusted pull-request-controlled code, load untrusted tool configuration, or run with powerful secrets/tokens in the same environment.

## Current capabilities

- Tier 1: Capability Engine
- Tier 2: Review Intelligence
- Tier 3: Evidence Consensus
- Tier 4: Verified Learning Loop
- Tier 5: Graduation Benchmark
- Tier 6: Squad Intelligence
- App bridge for integrations
- Read-only live GitHub PR comment fetch
- Public safety boundary checks

## Useful commands

```bash
main-review review . --pretty
main-review app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
main-review live-github-comments owner/repo 12 --pretty
main-review boundary execute_pr_code --pretty
main-review visibility-policy --pretty
```

## Status

Sergeant's v1 foundation is implemented and self-verifying.

The current self-check target is:

```bash
main-review verify-standard --pretty
```

A complete self-check returns:

```json
{
  "status": "verified",
  "next_actions": []
}
```

## Research sources

Key starting references:

- Kudelski Security: CodeRabbit exploit technical write-up — https://kudelskisecurity.com/research/how-we-exploited-coderabbit-from-a-simple-pr-to-rce-and-write-access-on-1m-repositories
- Endor Labs: PwnedRabbit architectural lessons — https://www.endorlabs.com/learn/when-coderabbit-became-pwnedrabbit-a-cautionary-tale-for-every-github-app-vendor-and-their-customers
- CodeRabbit response — https://www.coderabbit.ai/blog/our-response-to-the-january-2025-kudelski-security-vulnerability-disclosure-action-and-continuous-improvement
- Qodo/PR-Agent open-source reviewer lineage — https://github.com/qodo-ai/pr-agent
- reviewdog — https://github.com/reviewdog/reviewdog
- Semgrep — https://semgrep.dev/
- CodeQL — https://codeql.github.com/
