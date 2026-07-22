"""Fail-closed validation for Sergeant Actions evidence ledgers.

The ledger records preservation state. It does not delete artifacts or workflow
runs and cannot grant cleanup authority by inference.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping, Sequence

LEDGER_SCHEMA_VERSION = "sergeant.actions-evidence-ledger.v1"
REPLAY_SCHEMA_VERSION = "sergeant.actions-recovery-replay.v1"
CLEANUP_MANIFEST_SCHEMA_VERSION = "sergeant.actions-cleanup-manifest.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_timestamp(value: object) -> bool:
    if not _non_empty_string(value):
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_preservation_ledger(payload: object) -> list[str]:
    """Return every integrity error found in a preservation ledger."""

    if not isinstance(payload, Mapping):
        return ["Actions evidence ledger root must be an object"]

    errors: list[str] = []
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        errors.append("unsupported Actions evidence ledger schema")
    if not _non_empty_string(payload.get("repository")):
        errors.append("ledger repository is required")
    if not _non_empty_string(payload.get("durable_root")):
        errors.append("ledger durable_root is required")
    if not _valid_timestamp(payload.get("generated_at")):
        errors.append("ledger generated_at must be a valid timestamp")
    if payload.get("deletion_authorized") is not False:
        errors.append("ledger must not authorize artifact deletion")
    if payload.get("workflow_run_deletion_authorized") is not False:
        errors.append("ledger must not authorize workflow-run deletion")

    records = payload.get("records")
    if not isinstance(records, list) or not records:
        return errors + ["ledger must contain preserved artifact records"]

    expected_count = payload.get("artifact_count")
    if expected_count != len(records):
        errors.append("artifact_count does not match records")

    names: set[str] = set()
    total_bytes = 0
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, Mapping):
            errors.append(f"{prefix} must be an object")
            continue

        name = record.get("name")
        if not _non_empty_string(name):
            errors.append(f"{prefix}.name is required")
        elif name in names:
            errors.append(f"duplicate artifact name: {name}")
        else:
            names.add(name)

        size = record.get("size_bytes")
        if type(size) is not int or size < 0:
            errors.append(f"{prefix}.size_bytes must be a non-negative integer")
        else:
            total_bytes += size

        digest = record.get("sha256")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            errors.append(f"{prefix}.sha256 must be a lowercase SHA-256 digest")

        if record.get("size_verified") is not True:
            errors.append(f"{prefix} durable-copy size is not verified")
        if record.get("deletion_authorized") is not False:
            errors.append(f"{prefix} must remain non-deletable")
        if not _non_empty_string(record.get("durable_folder")):
            errors.append(f"{prefix}.durable_folder is required")

        github = record.get("github")
        source = record.get("source")
        if github is None and source != "recovered_local_evidence_cache":
            errors.append(f"{prefix} lacks source provenance")
        if github is not None:
            if not isinstance(github, Mapping):
                errors.append(f"{prefix}.github must be an object")
            else:
                for key in ("artifact_id", "workflow_run_id", "head_sha", "expires_at"):
                    if github.get(key) in (None, ""):
                        errors.append(f"{prefix}.github.{key} is required")

    if payload.get("total_bytes") != total_bytes:
        errors.append("total_bytes does not match record sizes")
    return errors


def validate_recovery_replay(
    ledger: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> list[str]:
    """Verify that downloaded durable copies exactly match the preservation ledger."""

    errors = validate_preservation_ledger(ledger)
    if replay.get("schema_version") != REPLAY_SCHEMA_VERSION:
        errors.append("unsupported Actions recovery replay schema")
    if replay.get("cleanup_authorized") is not False:
        errors.append("replay must not authorize artifact cleanup")
    if replay.get("workflow_run_deletion_authorized") is not False:
        errors.append("replay must not authorize workflow-run deletion")

    ledger_records = ledger.get("records")
    replay_records = replay.get("records")
    if not isinstance(ledger_records, list) or not isinstance(replay_records, list):
        return errors + ["ledger and replay records must be lists"]

    def keyed(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                errors.append(f"{label}[{index}] must be an object")
                continue
            name = record.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"{label}[{index}].name is required")
                continue
            if name in result:
                errors.append(f"duplicate {label} name: {name}")
                continue
            result[name] = record
        return result

    ledger_by_name = keyed(ledger_records, "ledger_records")
    replay_by_name = keyed(replay_records, "replay_records")
    if set(ledger_by_name) != set(replay_by_name):
        missing = sorted(set(ledger_by_name) - set(replay_by_name))
        extra = sorted(set(replay_by_name) - set(ledger_by_name))
        if missing:
            errors.append(f"replay missing artifacts: {', '.join(missing)}")
        if extra:
            errors.append(f"replay contains unknown artifacts: {', '.join(extra)}")

    for name in sorted(set(ledger_by_name) & set(replay_by_name)):
        source = ledger_by_name[name]
        recovered = replay_by_name[name]
        if recovered.get("recovery_replay_verified") is not True:
            errors.append(f"recovery replay not verified: {name}")
        if recovered.get("size_bytes") != source.get("size_bytes"):
            errors.append(f"recovery size mismatch: {name}")
        if recovered.get("sha256") != source.get("sha256"):
            errors.append(f"recovery digest mismatch: {name}")

    verified = sum(
        record.get("recovery_replay_verified") is True
        for record in replay_by_name.values()
    )
    total_bytes = retained_bytes(replay_by_name.values())
    if replay.get("artifact_count") != len(replay_by_name):
        errors.append("replay artifact_count does not match records")
    if replay.get("verified_count") != verified:
        errors.append("replay verified_count does not match records")
    if replay.get("failed_count") != len(replay_by_name) - verified:
        errors.append("replay failed_count does not match records")
    if replay.get("total_bytes") != total_bytes:
        errors.append("replay total_bytes does not match records")
    if replay.get("artifact_count") != ledger.get("artifact_count"):
        errors.append("replay artifact_count does not match preservation ledger")
    if replay.get("total_bytes") != ledger.get("total_bytes"):
        errors.append("replay total_bytes does not match preservation ledger")
    return errors


def cleanup_eligible(
    record: Mapping[str, Any],
    *,
    cleanup_manifest: Mapping[str, Any] | None,
    recovery_replay_verified: bool,
    content_equivalent: bool,
) -> bool:
    """Return true only for an exact-artifact authorized, replayed duplicate."""

    github = record.get("github")
    artifact_id = github.get("artifact_id") if isinstance(github, Mapping) else None
    manifest_matches = bool(
        isinstance(cleanup_manifest, Mapping)
        and cleanup_manifest.get("schema_version") == CLEANUP_MANIFEST_SCHEMA_VERSION
        and cleanup_manifest.get("owner_authorized") is True
        and type(cleanup_manifest.get("artifact_id")) is int
        and cleanup_manifest.get("artifact_id") == artifact_id
    )
    return bool(
        manifest_matches
        and recovery_replay_verified
        and content_equivalent
        and type(artifact_id) is int
        and record.get("size_verified") is True
        and isinstance(record.get("sha256"), str)
        and _SHA256.fullmatch(record["sha256"]) is not None
        and record.get("deletion_authorized") is True
    )


def retained_bytes(records: Sequence[Mapping[str, Any]]) -> int:
    """Return the total byte count represented by valid integer sizes."""

    return sum(
        size
        for record in records
        if type((size := record.get("size_bytes"))) is int and size >= 0
    )
