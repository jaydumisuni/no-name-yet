# Sergeant

**Sergeant** is an open-source engineering reviewer for repositories and pull requests.

It helps developers understand code changes before they are merged by analyzing engineering quality, identifying risks, and providing evidence-based review decisions.

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

---

## Works With

Sergeant integrates into existing development workflows.

Supported platforms include:

- GitHub
- VS Code *(coming soon)*
- JetBrains IDEs *(coming soon)*

Sergeant can also be used alongside coding assistants such as:

- Claude
- Codex
- GitHub Copilot
- Cursor
- Gemini
- Local LLMs

Sergeant reviews independently—it does not depend on any specific coding assistant.

---

## Review Outcomes

Every review produces one of three outcomes:

```text
PASS
NEEDS WORK
BLOCK
```

Along with supporting evidence, affected files, reasoning, confidence, and recommended next steps.

---

## Safety

Sergeant is a reviewer, not an execution engine.

It will not:

- execute untrusted pull request code
- automatically modify project code
- write patches by itself
- silently ignore review failures
- use privileged write credentials during analysis

---

## Installation

```bash
git clone https://github.com/jaydumisuni/Sergeant.git
cd Sergeant
```

*(Installation guide will expand as packages become available.)*

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

Documentation is organised by topic:

- Getting Started
- Installation
- CLI Reference
- GitHub Integration
- IDE Bench *(coming soon)*
- Security
- Architecture
- Contributing

---

## Current Status

Sergeant is under active development.

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

---

## Contributing

Contributions, issue reports, feature requests, and engineering discussions are welcome.

If you'd like to help improve Sergeant, please open an issue or submit a pull request.