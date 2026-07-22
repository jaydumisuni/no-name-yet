"""Fail-closed validation for Sergeant Actions evidence ledgers.

The ledger records preservation state. It does not delete artifacts or workflow
runs and cannot grant cleanup authority by inference.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

LEDGER_SCHEMA_VERSION = "sergeant.actions-evidence-ledger.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_preservation_ledger(payload: Mapping[str, Any]) -> list[str]:
    """Return every integrity error found in a preservation ledger."""

    errors: list[str] = []
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        errors.append("unsupported Actions evidence ledger schema")
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
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}.name is required")
        elif name in names:
            errors.append(f"duplicate artifact name: {name}")
        else:
            names.add(name)

        size = record.get("size_bytes")
        if not isinstance(size, int) or size < 0:
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
        if not isinstance(record.get("durable_folder"), str) or not record.get("durable_folder"):
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


def cleanup_eligible(
    record: Mapping[str, Any],
    *,
    owner_authorized: bool,
    recovery_replay_verified: bool,
    content_equivalent: bool,
) -> bool:
    """Return true only for an explicitly authorized, replayed duplicate.

    The record itself must name the exact GitHub artifact and carry the durable
    digest. Unknown or locally recovered evidence never becomes eligible through
    this helper.
    """

    github = record.get("github")
    return bool(
        owner_authorized
        and recovery_replay_verified
        and content_equivalent
        and isinstance(github, Mapping)
        and isinstance(github.get("artifact_id"), int)
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
        if isinstance((size := record.get("size_bytes")), int) and size >= 0
    )
