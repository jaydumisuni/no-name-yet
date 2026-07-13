from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VSCODE_ROOT = ROOT / "src" / "vscode"


def test_vscode_extension_manifest_installs_sergeant_commands() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    commands = {item["command"] for item in package["contributes"]["commands"]}
    containers = package["contributes"]["viewsContainers"]["activitybar"]
    properties = package["contributes"]["configuration"]["properties"]

    assert "activationEvents" not in package
    assert package["displayName"] == "Sergeant"
    assert package["version"] == "0.4.0"
    assert package["icon"] == "resources/srg-logo-and-icon.png"
    assert package["main"] == "./src/vscode/extension.js"
    assert (ROOT / package["main"]).is_file()
    assert containers[0]["id"] == "sergeant"
    assert containers[0]["title"] == "Sergeant"
    assert containers[0]["icon"] == "resources/sergeant-activity.svg"
    assert (ROOT / containers[0]["icon"]).is_file()
    for command in {
        "sergeant.openCommandCenter",
        "sergeant.reviewWorkspace",
        "sergeant.appReviewWorkspace",
        "sergeant.reviewCurrentFile",
        "sergeant.reviewChangedFiles",
        "sergeant.v2Mission",
        "sergeant.proofSuite",
        "sergeant.finalProof",
        "sergeant.verifyStandard",
        "sergeant.battleTests",
        "sergeant.ideBenchContract",
        "sergeant.openLastReport",
        "sergeant.copyLastReport",
        "sergeant.exportLastReport",
    }:
        assert command in commands
    assert (ROOT / package["icon"]).is_file()
    assert properties["sergeant.provider"]["default"] == "Automatic Open-Source Review"
    assert properties["sergeant.llmPolicy"]["default"] == "preferred"
    assert properties["sergeant.llmProvider"]["default"] == "auto"
    assert properties["sergeant.llmCouncil"]["default"] == "adaptive"
    assert "fcc" in properties["sergeant.llmProvider"]["enum"]
    assert "openai-compatible" in properties["sergeant.llmProvider"]["enum"]


def test_vscode_runtime_uses_bundled_full_command_center() -> None:
    extension = (VSCODE_ROOT / "extension.js").read_text(encoding="utf-8")
    actions = (VSCODE_ROOT / "actions.js").read_text(encoding="utf-8")
    provider = (VSCODE_ROOT / "command-center.js").read_text(encoding="utf-8")
    results = (VSCODE_ROOT / "results.js").read_text(encoding="utf-8")
    command_center = (ROOT / "resources" / "sergeant-command-center-v2.html").read_text(encoding="utf-8")
    command_center_css = (ROOT / "resources" / "sergeant-command-center-v2.css").read_text(encoding="utf-8")
    command_center_js = (ROOT / "resources" / "sergeant-command-center-v2.js").read_text(encoding="utf-8")

    assert 'path.join(extensionRoot, "sergeant.py")' in extension
    assert "registerWebviewViewProvider" in extension
    assert "SergeantCommandCenterProvider" in extension
    assert "semanticEnvironment" in extension
    assert "SERGEANT_LLM_PROVIDER" in extension
    assert "SERGEANT_LLM_COUNCIL" in extension
    assert "openFullCommandCenter" in provider
    assert "saveSemanticSettings" in provider
    assert "LLM_SETTING_KEYS" in provider
    assert "sergeant-command-center-v2.html" in provider
    assert "SERGEANT_HOST_BOOTSTRAP" in provider
    assert "createWebviewPanel" in extension
    assert "renderResultHtml" in extension
    assert "Required Actions" in results
    assert "Top Findings" in results
    assert "Raw Evidence" in results

    for action in [
        '"pr-review"',
        '"app-review"',
        '"v2-mission"',
        '"proof-suite"',
        '"final-proof"',
        '"verify-standard"',
        '"battle-tests"',
        '"ide-bench-contract"',
    ]:
        assert action in actions

    for expected in [
        "SERGEANT V2 — Command Center",
        "Mission Planner",
        "Evidence Locker",
        "Officer System / Armoury",
        "Semantic Review Router",
        "Free Claude Code (FCC)",
        "GLM-5.2",
        "Qwen3-Coder-Next",
        "Kimi K2.5",
        "Pass to Writer",
        "Sergeant V2 Review Doctrine",
        "Post‑V2 Roadmap",
        "◇ What is Sergeant?",
        "Commander → Mission → Officers → Weapon Manifest → Evidence → Verdict → Audit Trail",
        "Semantic Evidence",
    ]:
        assert expected in command_center
    assert "sergeantHostSend" in command_center_js
    assert "saveSemanticSettings" in command_center_js
    assert "window.addEventListener('message'" in command_center_js
    assert "Deterministic Evidence → Semantic Evidence → Verification" in command_center_js
    assert "grid-template-columns:270px" in command_center_css
    assert "Math.random" not in command_center_js
    assert "sgtTimer" not in command_center_js


def test_command_center_visible_controls_are_wired() -> None:
    extension = (VSCODE_ROOT / "extension.js").read_text(encoding="utf-8")
    actions = (VSCODE_ROOT / "actions.js").read_text(encoding="utf-8")
    provider = (VSCODE_ROOT / "command-center.js").read_text(encoding="utf-8")
    command_center = (ROOT / "resources" / "sergeant-command-center-v2.html").read_text(encoding="utf-8")
    command_center_js = (ROOT / "resources" / "sergeant-command-center-v2.js").read_text(encoding="utf-8")

    for action_id in [
        "reviewWorkspace",
        "appReviewWorkspace",
        "reviewCurrentFile",
        "reviewChangedFiles",
        "v2Mission",
        "proofSuite",
        "finalProof",
        "verifyStandard",
        "battleTests",
        "ideBenchContract",
    ]:
        assert f'id: "{action_id}"' in actions

    for message_type in [
        "run",
        "openFull",
        "openLast",
        "copyLast",
        "exportLast",
        "selectWorkspace",
        "saveSettings",
        "refresh",
        "ready",
    ]:
        assert f'"{message_type}"' in provider or f"'{message_type}'" in command_center_js

    for control_id in [
        "deployBtn",
        "openLatestReport",
        "exportBattleReport",
        "copyVerdict",
        "providerSelect",
        "llmPolicySelect",
        "llmModelInput",
        "llmBaseUrlInput",
        "llmProtocolSelect",
        "llmCouncilSelect",
        "workspaceSelect",
        "globalSearch",
        "quickCopy",
    ]:
        assert f'id="{control_id}"' in command_center

    assert "onDidReceiveMessage" in provider
    assert "handleMessage" in provider
    assert "copyLastReport" in extension
    assert "exportLastReport" in extension
    assert "context.globalState" in provider


def test_command_center_has_single_mission_execution_boundary() -> None:
    extension = (VSCODE_ROOT / "extension.js").read_text(encoding="utf-8")
    command_center = (ROOT / "resources" / "sergeant-command-center-v2.html").read_text(encoding="utf-8")
    visual_proof = (ROOT / "tests" / "command-center-visual.spec.js").read_text(encoding="utf-8")
    closure = (ROOT / "docs" / "04-command-center-review-closure.md").read_text(encoding="utf-8")

    assert "let activeRun = null" in extension
    assert "clearActiveRun" in extension
    assert "is already running" in extension
    assert "activeRun.child.kill()" in extension
    assert "let missionLocked = false" in command_center
    assert "event.stopImmediatePropagation()" in command_center
    assert "queueMicrotask" in command_center
    assert "window.sergeantMissionLock" in command_center
    assert "sends only one mission while a run is active" in visual_proof
    assert "toHaveLength(1)" in visual_proof
    assert ".github/workflows/multiplatform-proof.yml" in closure
    assert "scripts/build-command-center-preview.js" in closure
    assert "one active mission per IDE host" in closure
