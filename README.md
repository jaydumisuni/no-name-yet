# Sergeant

**Sergeant** is an open-source engineering reviewer that helps developers review repositories and pull requests before code is merged.

Instead of writing code, Sergeant focuses on understanding it—analyzing changes, identifying risks, and providing evidence-based review decisions that help teams build with confidence.

---

## Features

- Repository review
- Pull request & diff review
- Cross-file dependency analysis
- Architecture review
- Data-flow analysis
- Security analysis
- API contract verification
- Performance analysis
- Test impact analysis
- Regression prediction
- Secret detection
- Documentation vs implementation verification
- Multi-language support
- Evidence-based review reports
- Live GitHub read-only fetch
- CLI review workflow
- App Bridge review handoff
- IDE Bench contract for VS Code, JetBrains, and AI handoff
- Battle-test benchmark framework

---

## Why Sergeant?

Most AI coding assistants focus on writing code.

Sergeant focuses on reviewing it.

Rather than replacing your existing tools, Sergeant works alongside them by providing independent engineering reviews before code is merged.

---

## Works With

Sergeant fits naturally into existing development workflows.

Platforms:

- GitHub
- CLI
- App Bridge
- IDE Bench contract for VS Code and JetBrains handoff
- VS Code *(contract ready)*
- JetBrains IDEs *(contract ready)*

Compatible with:

- Claude
- Codex
- GitHub Copilot
- Cursor
- Gemini
- Local LLMs

Sergeant remains an independent reviewer regardless of which coding assistant you use.

---

## Review Outcomes

Every review produces one of three outcomes:

```text
PASS
NEEDS WORK
BLOCK
```

Each review includes supporting evidence, affected files, reasoning, confidence, and recommended next steps.

---

## Safety

Sergeant is a reviewer—not an execution engine.

It deliberately refuses to:

- Execute untrusted pull request code
- Automatically modify project code
- Write patches by itself
- Use privileged write credentials during analysis
- Hide review failures or fabricate successful results

---

## Installation

```bash
git clone https://github.com/jaydumisuni/Sergeant.git
cd Sergeant
```

---

## Quick Start

Review the current repository:

```bash
main-review review . --pretty
```

Review a pull request:

```bash
main-review app-review . --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Review live GitHub comments:

```bash
main-review live-github-comments owner/repo 12 --pretty
```

---

## Documentation

Documentation includes:

- Getting Started
- Installation
- CLI Reference
- GitHub Integration
- IDE Bench
- Security
- Architecture
- Contributing
- Hackathon submission brief: `docs/hackathon-submission.md`
- Submission proof: `docs/submission-proof.md`
- Submission readiness gate: `SUBMISSION_READY.md`

---

## Current Status

Sergeant is ready for early adopters and community feedback.

Current capabilities include:

- Repository intelligence
- Pull request review
- Cross-file reasoning
- Architecture analysis
- Security review
- Regression prediction
- Verified learning
- Squad-based review intelligence
- Read-only GitHub review ingestion
- CLI integration
- App Bridge integration
- IDE Bench contract
- CI and clean-clone proof
- Battle-test framework with Requests and Flask architecture benchmarks

### Submission proof status

The current sprint completed:

- Live GitHub read-only fetch
- CLI integration
- App Bridge integration
- IDE Bench contract
- Mocked tests
- CI proof
- Clean-clone proof
- Battle-test framework
- Requests benchmark
- Flask architecture benchmark
- Battle-test validator
- Release proof through PR where CI and Main Review are green

Honest proof boundary:

- Secret detection is genuinely proven with a planted temporary-file positive case.
- GitHub PR comment payload ingestion is verified using GitHub-shaped fixtures.
- Full live GitHub API ingestion should be claimed only after a real API call is captured and saved.

---

## Contributing

Contributions, issue reports, feature requests, and engineering discussions are welcome.

If you'd like to help improve Sergeant, please open an issue or submit a pull request.
