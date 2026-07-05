"""IDE Bench contract for Sergeant integrations.

The IDE layer does not run a different reviewer. VS Code, PyCharm, JetBrains,
and AI tools all hand off the same review request shape to the app bridge and
receive the same review response shape back.
"""
from __future__ import annotations

from typing import Any

from .review_contract import CONTRACT_VERSION, capability_names

SERGEANT_ICON_ASSET = "resources/srg-logo-and-icon.png"

AI_HANDOFF_CONTRACT = {
    "schema_version": CONTRACT_VERSION,
    "principle": "Sergeant is a read-only reviewer. IDEs and AI tools submit evidence; they do not get write privileges through this contract.",
    "request": {
        "root": "string path to repository root",
        "mode": "repository | pull_request | changed_files",
        "changed_files": "array of repository-relative paths or comma/newline string",
        "external_providers": "optional reviewer evidence packets from bots, tools, or human review notes",
        "human_decisions": "optional accepted/rejected decision evidence for learning loop",
        "write_learning": "boolean; defaults to false",
        "sergeant_benchmark": "optional Sergeant benchmark metrics",
        "reference_benchmark": "optional comparison benchmark metrics",
    },
    "response": {
        "schema_version": CONTRACT_VERSION,
        "status": "pass | needs_work | block",
        "action": "APPROVE | COMMENT | REQUEST_CHANGES",
        "confidence": "0..1",
        "required_actions": "array of concrete review actions",
        "capabilities": capability_names(),
        "markdown": "human-readable review body",
        "packet": "full evidence packet for audit/debugging",
    },
}


def vscode_interface() -> dict[str, Any]:
    return {
        "name": "VS Code",
        "entrypoint": "sergeant.review",
        "icon_asset": SERGEANT_ICON_ASSET,
        "transport": "local process, extension host, or app bridge HTTP wrapper",
        "request_format": CONTRACT_VERSION,
        "response_format": CONTRACT_VERSION,
        "minimum_commands": [
            "Review Workspace",
            "Review Changed Files",
            "Review Pull Request",
            "Compare External Reviewer Evidence",
        ],
        "handoff": AI_HANDOFF_CONTRACT,
    }


def pycharm_interface() -> dict[str, Any]:
    return {
        "name": "PyCharm",
        "vendor_family": "JetBrains",
        "entrypoint": "SergeantReviewAction",
        "icon_asset": SERGEANT_ICON_ASSET,
        "transport": "IDE action, local process, or app bridge HTTP wrapper",
        "request_format": CONTRACT_VERSION,
        "response_format": CONTRACT_VERSION,
        "minimum_actions": [
            "Review Project",
            "Review Changelist",
            "Review Pull Request",
            "Compare External Reviewer Evidence",
        ],
        "handoff": AI_HANDOFF_CONTRACT,
    }


def jetbrains_interface() -> dict[str, Any]:
    return {
        "name": "JetBrains",
        "entrypoint": "SergeantReviewAction",
        "icon_asset": SERGEANT_ICON_ASSET,
        "transport": "IDE action, local process, or app bridge HTTP wrapper",
        "request_format": CONTRACT_VERSION,
        "response_format": CONTRACT_VERSION,
        "minimum_actions": [
            "Review Project",
            "Review Changelist",
            "Review Pull Request",
            "Compare External Reviewer Evidence",
        ],
        "handoff": AI_HANDOFF_CONTRACT,
    }


def build_ide_bench_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": CONTRACT_VERSION,
        "service": "Sergeant IDE Bench",
        "interfaces": {
            "vscode": vscode_interface(),
            "pycharm": pycharm_interface(),
            "jetbrains": jetbrains_interface(),
        },
        "ai_handoff_contract": AI_HANDOFF_CONTRACT,
    }
