# Repository Intelligence Engine

The Repository Intelligence Engine is the first implementation layer of Main Review.

Its job is not to judge code yet.

Its first job is to answer:

> What am I looking at?

## Language strategy

Languages are easy for AI to reason about once they are identified, so the first scanner is broad from the start.

Initial detection includes:

- Python
- JavaScript
- TypeScript
- HTML
- CSS / SCSS
- JSON
- YAML
- TOML
- Markdown
- Shell
- PowerShell
- Dockerfile
- SQL
- R / RMarkdown
- Go
- Rust
- Java
- Kotlin
- C
- C++
- C#
- PHP
- Ruby
- Swift
- Dart
- Lua
- XML
- INI/config files

The scanner is language-aware first, language-complete later.

## First output

The scanner builds a static context packet:

```json
{
  "total_files": 10,
  "languages": {
    "Python": 4,
    "R": 1,
    "Markdown": 2
  },
  "roles": {
    "source": 4,
    "test": 2,
    "documentation": 2
  },
  "high_risk_files": [".github/workflows/ci.yml"],
  "docs": ["README.md"],
  "tests": ["tests/test_app.py"],
  "manifests": ["pyproject.toml"]
}
```

## Safety rule

The scanner does not execute project code.

It only walks files and classifies them.

This keeps Patch 01 aligned with the PwnedRabbit lesson:

> Understand danger, but do not execute danger.

## CLI

```bash
main-review scan --pretty
```

## Why this matters

A reviewer that does not understand the repository has no business judging a PR.

This engine gives future review layers the project map they need before reasoning starts.