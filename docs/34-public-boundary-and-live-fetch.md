# Public Boundary and Live GitHub Fetch

Sergeant is public/open-source review infrastructure.

It can be used inside THETECHGUY/Hunter, but private project rules, private memories, customer evidence, and deployment secrets must stay outside the public repository.

## Public-safe capability

`main_review/github_live_fetch.py` provides production-hardened, read-only GitHub pull-request evidence ingestion.

It is intentionally separate from `github_collector.py`:

- `github_collector.py` stays a pure parser.
- `github_live_fetch.py` is the only built-in module that performs GitHub PR comment network fetches.
- `github_diff_fetch.py` reuses the same validated host, identity, and pagination boundary for PR file patches.

## Security boundary

Allowed:

- GET-only public API fetch
- optional read-only token from an environment variable
- explicitly allowlisted GitHub Enterprise API host
- static review
- external evidence ingestion
- verified learning from human outcomes

Refused:

- running pull-request supplied project code during review
- running shell commands from PR content
- using advertised write-capable classic token scopes
- arbitrary API hosts, ports, paths, redirects, or pagination targets
- private repository evidence unless explicitly enabled locally
- silently converting fetch failures into empty comments
- writing patches as part of review
- exposing comment bodies in shareable proof artifacts

## CLI

```bash
export GITHUB_TOKEN=<read-only-token>
main-review live-github-comments jaydumisuni/Sergeant 77 \
  --token-env GITHUB_TOKEN \
  --proof-only \
  --proof-output build/live-github-proof.json \
  --pretty

main-review boundary run_untrusted_code --pretty
main-review visibility-policy --pretty
```

Tokens are read from environment variables rather than command-line values.

## Proven testing claim

Secret detection is proven by a planted temporary-file positive case.

GitHub PR ingestion has three proof layers:

1. network-free payload parsing through `github_collector.py`;
2. adversarial mocked transport tests for host, identity, pagination, token-scope, redaction, redirect, and private-boundary behavior;
3. a real read-only GitHub Actions workflow that fetches the triggering pull request's metadata, issue comments, and review comments.

The workflow is:

```text
.github/workflows/live-github-ingestion-proof.yml
```

It uploads a sanitized artifact containing request evidence, pull-request identity, counts, SHA-256 body hashes, token-scope assessment, and proof claims. It does not upload comment bodies or credentials.

Full details: [`36-production-hardening.md`](36-production-hardening.md).
