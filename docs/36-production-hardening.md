# Phase 7 — Production Hardening

## Status

Implemented and proof-gated through repository tests plus a real read-only GitHub API workflow.

This phase does not give Sergeant new authority. It makes the existing reviewer boundary enforceable instead of relying on descriptions alone.

## Enforced boundary

Sergeant remains:

- read-only by default;
- unable to execute pull-request-controlled code;
- unable to grant itself repository write authority;
- unable to use a write-capable token when classic scope evidence is advertised;
- unable to materialize fetched PR paths outside its temporary sandbox;
- unable to silently treat unknown actions or policy profiles as safe.

Unknown actions are denied until explicitly added to the public allowlist.

## Sandbox enforcement

External file paths are normalized against a resolved repository root.

Refused inputs include:

- absolute file paths;
- `..` traversal;
- symlink escape;
- NUL-containing paths;
- changed-file lists above the configured safety limit;
- PR filenames that would escape the temporary battle workspace.

## Permission policy

Public profiles:

```text
default
public
public-review
pull-request-review
```

Public profiles may request read-only network access, but cannot enable:

```text
allow_shell
allow_write
allow_untrusted_code
read_only=false
```

Elevated local profiles require:

```text
SERGEANT_ALLOW_ELEVATED_MISSIONS=true
```

Even elevated profiles cannot grant repository writes or execution of pull-request-controlled code.

## GitHub live-ingestion security

Live GitHub evidence now verifies:

1. a plain `owner/repo` slug;
2. an HTTPS allowlisted GitHub API host;
3. the requested PR number;
4. the PR base repository identity;
5. public visibility unless private evidence is explicitly enabled;
6. GET-only request evidence;
7. same-host, same-repository pagination;
8. bounded page count;
9. advertised token scopes;
10. expected JSON payload shapes.

The default trusted host is:

```text
api.github.com
```

GitHub Enterprise hosts must be explicitly listed with either:

```text
--allowed-host github.example.com
```

or:

```text
SERGEANT_GITHUB_ALLOWED_HOSTS=github.example.com
```

HTTP is refused except an explicitly enabled loopback test endpoint.

## Token handling

CLI tokens are read from an environment variable rather than passed as command-line values:

```bash
main-review live-github-comments owner/repo 123 \
  --token-env GITHUB_TOKEN \
  --proof-only \
  --pretty
```

When GitHub advertises classic OAuth scopes, known write-capable scopes such as `repo`, `public_repo`, `workflow`, `write:*`, and `admin:*` are rejected.

Fine-grained and Actions tokens do not always advertise granted scopes in response headers. In that case the proof records `not-advertised`; the GitHub Actions proof workflow separately constrains `GITHUB_TOKEN` to:

```yaml
permissions:
  contents: read
  issues: read
  pull-requests: read
```

## Public/private leak control

Known credential shapes in fetched comment bodies and API errors are replaced with:

```text
[REDACTED_SECRET]
```

The shareable proof artifact never contains comment bodies. It contains only:

- repository and PR identity;
- sanitized base/head metadata;
- request method/status/page evidence;
- comment counts;
- SHA-256 hashes of comment bodies;
- token-scope assessment;
- redaction count;
- explicit proof claims.

## Full live API proof

Workflow:

```text
.github/workflows/live-github-ingestion-proof.yml
```

The workflow runs against the real pull request that triggered it, using the repository-scoped read-only `GITHUB_TOKEN`. It performs the live metadata, issue-comment, and review-comment requests, validates the proof contract, and uploads:

```text
live-github-ingestion-proof/live-github-proof.json
```

This closes the earlier boundary between mocked payload parsing and a real network ingestion run without uploading comment bodies or secrets.

## Adversarial tests

Phase 7 proof covers:

- sandbox traversal;
- absolute path escape;
- symlink escape;
- malicious changed-file lists;
- unknown action default denial;
- allowed-action context escalation;
- shell/write/untrusted-code permission escalation;
- unknown policy profiles and permission keys;
- unbounded time budgets;
- repository slug spoofing;
- API host SSRF attempts;
- pagination host/repository escape;
- PR base-repository spoofing;
- private repository refusal;
- write-capable classic token scopes;
- credential redaction;
- body-free proof artifacts;
- PR patch workspace traversal.

## High-risk workflow assurance

### `.github/workflows/ci.yml`

- **Purpose:** run the complete repository test, clean-clone, live battle, verification, final-proof, end-to-end, independent-reviewer, and mocked-integration gates.
- **Permissions:** workflow-level `contents: read`; it receives no write, issue, pull-request mutation, package publication, or deployment permission.
- **Secrets:** `GITHUB_TOKEN` is consumed only through the process environment and passed to Sergeant by environment-variable name; no token value is printed, persisted, or supplied as a command-line argument.
- **Rollback:** revert the workflow change to the previous token-free battle command or disable the live battle step while preserving unit, verification, and final-proof gates. No repository state or external resource requires migration.
- **Proof:** CI runs all tests, generates three real battle outputs, uploads them, then enforces THETECHGUY verification, final proof, proof suite, independent reviewer, and mocked GitHub integration.

### `.github/workflows/live-github-ingestion-proof.yml`

- **Purpose:** prove real read-only GitHub API ingestion against the pull request that triggered the workflow.
- **Permissions:** explicit `contents: read`, `issues: read`, and `pull-requests: read`; no write permission is granted.
- **Secrets:** the repository-scoped `GITHUB_TOKEN` remains in the environment, is referenced only by variable name, and is excluded from the uploaded artifact. Comment bodies are also omitted.
- **Rollback:** delete or disable this isolated workflow without changing Sergeant runtime behavior; mocked and adversarial ingestion tests continue to run in normal CI.
- **Proof:** the job performs real metadata, issue-comment, and review-comment GET requests, verifies repository identity and proof claims, and uploads a sanitized JSON artifact containing counts, hashes, request evidence, and token-scope assessment.

## Remaining authority

Sergeant remains the reviewer and final deterministic authority. Cpl and the permanent officers operate inside this boundary. Neither model selection nor council agreement can override a production safety refusal.
