# Phase 8A — Standalone Self-Hosted Service

## Status

Implemented as the first complete Phase 8 product deployment surface.

Sergeant can now run as:

- a local self-hosted HTTP service;
- an installed Python console service;
- a hardened non-root container;
- the existing Command Center connected to real service APIs;
- an HMAC-verified GitHub webhook intake endpoint.

This phase does **not** add GitHub posting, patch application, repository writes, pull-request code execution, or automatic merging.

## Product boundary

```text
Browser / API client
        ↓
Standalone transport boundary
        ↓
Hardened App Bridge request contract
        ↓
Sergeant + Cpl + permanent officers
        ↓
Evidence / verdict / report
```

GitHub webhook intake remains a separate input lane:

```text
GitHub webhook
        ↓ HMAC verification + replay suppression
Normalized PR event packet
        ↓
Intake record only
```

The webhook endpoint does not automatically fetch code, run a review, post a comment, or merge a pull request.

## Start locally

Install from the repository:

```bash
python -m pip install .
sergeant-serve --workspace .
```

The default bind address is:

```text
http://127.0.0.1:8765
```

Loopback-only mode may run without a bearer token. It is intended for one-user local operation.

## Authenticated binding

Any non-loopback bind requires a service token.

Generate a random token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Store it in the environment:

```bash
export SERGEANT_SERVICE_TOKEN=<generated-value>
sergeant-serve --workspace . --host 0.0.0.0 --port 8765
```

The token is never emitted in the startup packet, API state, proof artifact, or service log.

The Command Center asks for the token when the protected API returns `401`. It stores the token in `sessionStorage`, not repository files or long-lived browser storage.

## Validate without binding

```bash
sergeant-serve --workspace . --check
```

This validates:

- workspace existence;
- bind/authentication policy;
- webhook-secret policy;
- request and rate limits;
- allowed browser origins;
- packaged Command Center resources;
- declared service capabilities.

## Command Center

The service assembles the existing Sergeant V2 Command Center from the same HTML, CSS, responsive CSS, and JavaScript resources used by the IDE surfaces.

The standalone host bridge makes these controls real:

- review workspace;
- review one repository-relative file;
- review a supplied changed-file list;
- run final proof;
- run battle fixtures;
- build an IDE Bench contract;
- run a V2 mission;
- refresh service state;
- save non-secret Cpl UI settings;
- open the latest report;
- export the latest report;
- copy the latest verdict/report;
- show the configured single-workspace boundary.

The service does not pretend to support multiple workspaces. Selecting another workspace explains that a separate service instance is required.

## API contract

Contract version:

```text
sergeant.standalone.v1
```

Endpoints:

| Method | Path | Purpose | Authentication |
| --- | --- | --- | --- |
| `GET` | `/health` | Minimal liveness/readiness check | Public |
| `GET` | `/` | Command Center | Public shell; protected data loads through API |
| `GET` | `/api/v1/capabilities` | Product and authority contract | Bearer token when configured |
| `GET` | `/api/v1/state` | Runtime, history, settings and latest mission state | Bearer token when configured |
| `POST` | `/api/v1/review` | Hardened App Bridge review | Bearer token when configured |
| `POST` | `/api/v1/missions` | Named Command Center mission | Bearer token when configured |
| `POST` | `/api/v1/settings` | In-memory non-secret UI settings | Bearer token when configured |
| `GET` | `/api/v1/reports/latest` | Latest mission/report packet | Bearer token when configured |
| `POST` | `/api/v1/github/webhook` | Signed GitHub event intake | HMAC signature |

## Enforced service restrictions

Every API review is rewritten to:

```json
{
  "read_only": true,
  "allow_network": false,
  "allow_shell": false,
  "allow_write": false,
  "allow_untrusted_code": false
}
```

The configured workspace root overrides any caller-supplied root.

The service also forces:

```text
write_learning = false
```

This prevents a network client from writing repository memory or changing reviewer doctrine.

Changed-file and current-file missions remain subject to the Phase 7 path-containment boundary.

## GitHub webhook intake

Set a separate webhook secret:

```bash
export SERGEANT_WEBHOOK_SECRET=<different-random-value>
```

Supported events:

- `ping`
- `pull_request`

Review-relevant pull-request actions:

- `opened`
- `synchronize`
- `reopened`
- `ready_for_review`

The endpoint verifies `X-Hub-Signature-256` using constant-time comparison, requires a delivery identifier, checks repository/base-repository identity, validates the PR number, and suppresses repeated delivery IDs during the service lifetime.

The normalized packet declares:

```text
authority = intake-only-no-posting
```

GitHub App installation authentication, check-run creation, review-comment posting, and durable delivery queues remain Phase 8B work.

## Request and browser controls

The service enforces:

- JSON-only POST bodies;
- bounded request size;
- per-client rate limits;
- exact CORS origins;
- same-origin Command Center access;
- bearer authentication when configured;
- one mission at a time;
- generic redacted error responses;
- no-store response caching;
- CSP, frame denial, MIME sniffing denial and restrictive browser permissions.

## Container deployment

Copy the environment template:

```bash
cp deploy/standalone.env.example .env
```

Generate and set `SERGEANT_SERVICE_TOKEN`, then run:

```bash
docker compose up --build
```

The Compose profile uses:

- a non-root `sergeant` user;
- a read-only root filesystem;
- the reviewed repository mounted read-only at `/workspace`;
- a small `/tmp` tmpfs;
- all Linux capabilities dropped;
- `no-new-privileges`;
- loopback-only host publishing;
- a public `/health` check;
- bearer authentication inside the container.

## Proof

Workflow:

```text
.github/workflows/standalone-service-proof.yml
```

It proves:

1. standalone adversarial unit tests;
2. source-runtime HTTP behavior;
3. configuration validation;
4. unauthenticated API refusal;
5. authenticated state and capabilities;
6. existing Command Center rendering with the standalone bridge;
7. a real repository-relative review mission;
8. mission-lock release after completion;
9. signed webhook acceptance;
10. webhook replay suppression;
11. body/token-free proof artifacts and logs;
12. wheel build and installed-resource discovery outside the source tree;
13. hardened Docker image build;
14. non-root/read-only/capability-dropped container runtime;
15. authenticated API access inside the container.

Artifacts:

```text
standalone-service-proof/standalone-service-proof.json
standalone-service-proof/standalone-service.log
standalone-service-proof/installed-wheel-check.json
standalone-service-proof/standalone-container-proof.json
standalone-service-proof/standalone-container.log
standalone-service-proof/sergeant_reviewer-*.whl
```

## High-risk deployment assurance

### `.github/workflows/standalone-service-proof.yml`

- **Purpose:** prove the standalone service from source, installed wheel and hardened container.
- **Permissions:** workflow-level `contents: read`; no issue, pull-request, package, deployment or repository write permission.
- **Secrets:** test tokens and webhook secrets are generated at runtime, masked, kept in process environments, excluded from command-line arguments, and checked against proof artifacts and logs.
- **Rollback:** remove the isolated workflow without changing Sergeant runtime behavior. Existing CI, Main Review, live-ingestion and multiplatform proof continue independently.
- **Proof:** unit tests, end-to-end HTTP proof, wheel installation, resource lookup, Docker build and constrained container runtime.

### `Dockerfile`

- **Purpose:** package the dependency-free standalone service and Command Center.
- **Permissions:** runs as the non-root `sergeant` user and contains no GitHub credential.
- **Secrets:** no build argument or secret is accepted; runtime tokens enter only through environment variables.
- **Rollback:** remove the image and use `sergeant-serve` directly from the Python installation.
- **Proof:** the dedicated workflow builds the image and runs authenticated health/state/UI checks under a read-only, capability-dropped container.

### `compose.yaml`

- **Purpose:** provide a reproducible local self-hosted deployment profile.
- **Permissions:** read-only repository mount, read-only container filesystem, all capabilities dropped, no-new-privileges and loopback-only published port.
- **Secrets:** `SERGEANT_SERVICE_TOKEN` is required from the operator environment; the optional webhook secret is separate.
- **Rollback:** `docker compose down` removes the service without modifying the reviewed repository.
- **Proof:** the declarations are regression-tested and the equivalent constrained container runtime is exercised in CI.

## Phase 8 boundary

Phase 8A completes a usable self-hosted product surface.

Phase 8B remains:

- GitHub App installation authentication;
- installation-token collector service;
- isolated comment/check poster;
- durable webhook delivery queue;
- installation/repository routing;
- signed audit exports;
- deployment behind a production reverse proxy.

Those capabilities must preserve the Zone 1 collector → Zone 2 analyzer → Zone 3 reasoner → Zone 4 poster separation from the security model.
