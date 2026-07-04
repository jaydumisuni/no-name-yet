# Research Sources

This repo studies review systems to extract principles, not to copy code or create hard dependencies.

## CodeRabbit / PwnedRabbit

### Kudelski Security

URL: https://kudelskisecurity.com/research/how-we-exploited-coderabbit-from-a-simple-pr-to-rce-and-write-access-on-1m-repositories

Why it matters:

- Shows how an AI review system can become a high-value GitHub App attack surface.
- Explains a practical chain from a pull request to remote code execution and access to sensitive credentials.
- Demonstrates that review tools must treat pull-request-controlled code and configuration as hostile.

Key lessons:

- Do not run untrusted repo configuration directly.
- Do not place privileged secrets in reviewer runtime.
- Do not combine analysis and write permissions.
- Flagging a dangerous PR is not enough if the system still executes it.

### Endor Labs

URL: https://www.endorlabs.com/learn/when-coderabbit-became-pwnedrabbit-a-cautionary-tale-for-every-github-app-vendor-and-their-customers

Why it matters:

- Converts the exploit into architecture lessons for GitHub App vendors and customers.
- Emphasizes least privilege, sandboxing, ephemeral credentials, and isolation.

Key lessons:

- Separate analysis from privileged GitHub operations.
- Use short-lived tokens.
- Avoid long-lived private keys inside execution workers.
- Micro-segment services and runners.

### CodeRabbit response

URL: https://www.coderabbit.ai/blog/our-response-to-the-january-2025-kudelski-security-vulnerability-disclosure-action-and-continuous-improvement

Why it matters:

- Shows how a commercial reviewer responded after disclosure.
- Useful for understanding expected remediation: disable risky execution paths, rotate secrets, sandbox tools, audit infrastructure, and add release/deployment gates.

## Qodo / PR-Agent

URL: https://github.com/qodo-ai/pr-agent

Why it matters:

- Open-source AI PR review system lineage.
- Useful for understanding commands, review summarization, PR descriptions, question answering, and structured review workflow.

Research focus:

- How review tasks are decomposed.
- How comments are generated.
- How providers/models are abstracted.
- How repository context is retrieved.
- How configuration is handled.

## reviewdog

URL: https://github.com/reviewdog/reviewdog

Why it matters:

- Strong pattern for turning linter/static-analysis output into PR review comments.
- Useful as a model for evidence ingestion and GitHub review posting.

Research focus:

- Diagnostic normalization.
- File/line mapping.
- Pull request comment placement.
- Tool-agnostic design.

## Semgrep

URL: https://semgrep.dev/

Why it matters:

- Semantic static analysis, security rules, and pattern matching.
- Good evidence source for code risk without relying only on LLM judgment.

Research focus:

- Rules as review evidence.
- Security and maintainability signals.
- Local versus cloud execution boundaries.

## CodeQL

URL: https://codeql.github.com/

Why it matters:

- Deep semantic code analysis and vulnerability detection.
- Useful as a future evidence provider, especially for security-sensitive repositories.

Research focus:

- Query-driven analysis.
- Security findings.
- SARIF output.
- CI integration.

## Sider / classic automated review tools

Sider is an example of automated review built around static analysis tools and PR comments.

Research focus:

- Low-noise review comments.
- Multi-language analyzer orchestration.
- PR-first developer workflow.

## Academic / architecture references

Useful themes from code-review research:

- Multi-agent review can separate roles such as vulnerability review, style review, consistency review, and final QA checking.
- Repository-level review needs context synthesis before file-level analysis.
- Automated review can improve awareness, but noisy or low-value comments slow teams down.

## Research rule

Every source must be studied for principles:

```text
What works?
What failed?
What can we learn?
What must we avoid?
What belongs in our reviewer?
What does not fit our philosophy?
```