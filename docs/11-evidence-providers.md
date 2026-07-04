# Evidence Providers

Evidence Providers are the third implementation layer of Main Review.

Their job is to produce facts. They do not produce the final verdict.

## Principle

```text
Evidence first.
Verdict later.
```

Patch 03 keeps providers static and safe. They do not execute project code.

## Included providers

### Secret scanner

Looks for sensitive values in text files.

Current patterns include:

- private key markers
- generic API key / token / password assignments
- GitHub token-like values
- AWS access key-like values

A detected secret is `blocker` severity.

### Test coverage checker

Checks whether source files exist without tests.

This is not full coverage analysis yet. It is an early signal that the project lacks proof.

### Documentation checker

Checks whether docs or README exist.

This supports the future rule that documentation must remain truthful and present.

### Risk path checker

Flags high-risk paths for review attention:

- `.github/workflows`
- scripts
- deployment folders
- infrastructure folders
- sensitive file extensions

Risk path findings are notes in v1. Later, changed risky paths in PRs may influence the verdict more strongly.

## CLI

```bash
main-review evidence --pretty
```

Example output:

```json
{
  "finding_count": 2,
  "findings": [
    {
      "provider": "test-coverage-checker",
      "severity": "major",
      "category": "testing",
      "message": "Source files exist but no tests were detected."
    }
  ]
}
```

## Why this matters

AI review without evidence becomes opinion.

Evidence Providers make the reviewer more reliable because they give the reasoning layer structured facts to weigh.

## What comes next

Later provider candidates:

- dependency scanner
- import graph checker
- duplicate module detector
- public/private boundary checker
- Semgrep provider
- CodeQL/SARIF importer
- reviewdog diagnostic importer
- documentation truth checker
- memory conflict checker

## Safety rule

Providers must not execute untrusted project scripts unless a future sandbox policy explicitly allows it.

The default is static inspection only.