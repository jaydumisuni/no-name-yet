# Sergeant V2 Command System

Status: Phase 1 implemented.

Sergeant V2 is an internal evolution of the V1 reviewer. It does not replace the
V1 CLI, app bridge, IDE contract, evidence consensus, squad, battle proof, or
release boundary.

The V2 command-system layer adds optional structured fields for:

- mission intake
- mission briefing
- shared services
- weapon manifests
- mission loadouts
- officer blueprints
- adaptive deployment
- adaptive confidence
- audit trail
- safety boundaries

The highest law remains:

> Sergeant commands. Specialists advise. Evidence decides.

## Public Contract

Existing V1 consumers keep using `sergeant.review.v1` responses. App Bridge
responses now include an optional `v2` packet. Consumers that do not read this
field continue to work.

## CLI

Build a V2 mission packet:

```bash
sergeant v2-mission . --mission-type pull_request_review --mode pull_request --files "src/app.py,tests/test_app.py" --pretty
```

Supported mission types:

- `repository_review`
- `pull_request_review`
- `changed_files_review`
- `single_file_review`
- `security_review`
- `architecture_review`
- `performance_review`
- `regression_review`
- `documentation_review`
- `benchmark_review`
- `learning_review`
- `emergency_review`
- `external_review_comparison`
- `release_gate_review`

## Safety

V2 remains read-only by default:

- no repository modification
- no untrusted code execution
- no write-token requirement
- network weapons disabled unless explicitly permitted
- shell/code execution disabled unless explicitly permitted

Weapons declare whether they execute code, require network, or modify files.
The loadout engine marks unavailable weapons instead of silently pretending they
ran.

## Phase Scope

This phase implements the command-system spine. It does not claim that every
future weapon or domain pack is complete. Future phases should add specialized
weapons, knowledge packs, battle analytics, and interface polish behind the same
stable mission contract.
