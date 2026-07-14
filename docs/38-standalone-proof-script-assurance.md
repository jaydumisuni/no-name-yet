# Standalone Runtime Proof Script Assurance

Target:

```text
scripts/prove-standalone-service.py
```

## Purpose

The script performs an end-to-end runtime proof of the Phase 8A standalone service. It validates configuration, starts a temporary loopback service, proves protected and public endpoints, runs one repository-relative review mission, verifies signed webhook intake and replay suppression, writes a sanitized proof artifact, and terminates the service.

It is proof automation only. It is not part of the long-running service and it does not modify reviewed source files.

## Permissions

The script runs with the permissions of the CI job or local operator.

Its service instance is restricted to:

- one configured repository workspace;
- read-only Sergeant review permissions;
- loopback HTTP binding;
- no repository write authority;
- no GitHub write authority;
- no shell or pull-request-controlled code execution;
- no automatic merge.

The script does not request GitHub Actions write permissions, package publication, deployment permissions, or privileged container access.

## Secrets

The script generates a random service token and a separate random webhook secret at runtime.

Both values:

- remain in the child-process environment;
- are never passed as command-line arguments;
- are never printed;
- are excluded from the JSON proof artifact;
- are checked against the completed proof artifact and service log before the script returns PASS.

No repository or organization secret is required.

## Rollback

Delete `scripts/prove-standalone-service.py` and remove its invocation from `.github/workflows/standalone-service-proof.yml`.

This rollback does not change the standalone service implementation, installed console command, Docker image, Compose profile, normal CI, Main Review, live GitHub ingestion proof, or multiplatform proof.

## Proof

The script proves:

1. `sergeant-serve --check` validates the service and packaged Command Center;
2. `/health` reaches ready state;
3. `/api/v1/state` rejects an unauthenticated request;
4. authenticated capabilities preserve no-write/no-execution authority;
5. the existing Command Center renders with `window.sergeantHostSend`;
6. a repository-relative current-file mission completes and returns a mission identifier;
7. the mission lock is released before the final state is returned;
8. a correctly signed GitHub `ping` event is accepted;
9. a repeated delivery identifier is suppressed;
10. service state records the review and webhook;
11. the proof artifact contains no service token or webhook secret;
12. the service log contains no service token or webhook secret.

Outputs:

```text
build/standalone-service-proof.json
build/standalone-service.log
```
