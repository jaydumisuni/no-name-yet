from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VSCODE_ROOT = ROOT / "src" / "vscode"


def test_vscode_extension_manifest_installs_sergeant_commands() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    commands = {item["command"] for item in package["contributes"]["commands"]}
    containers = package["contributes"]["viewsContainers"]["activitybar"]

    assert "activationEvents" not in package
    assert package["displayName"] == "Sergeant"
    assert package["version"] == "0.3.2"
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
    assert package["contributes"]["configuration"]["properties"]["sergeant.provider"]["default"] == "Local Model"


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
    assert "openFullCommandCenter" in provider
    assert "sergeant-command-center-v2.html" in provider
    assert "SERGEANT_HOST_BOOTSTRAP" in provider
    assert "createWebviewPanel" in extension
    assert "renderResultHtml" in extension
    assert "Required Actions" in results
    assert "Top Findings" in results
    assert "Raw Evidence" in results

    for action in [
        '"review"',
        '"app-review"',
        '"changed_files"',
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
        "AI / Provider Selector",
        "Pass to Writer",
        "Sergeant V2 Review Doctrine",
        "Post‑V2 Roadmap",
        "◇ What is Sergeant?",
        "Commander → Mission → Officers → Weapon Manifest → Evidence → Verdict → Audit Trail",
        "Runtime Evidence",
    ]:
        assert expected in command_center
    assert "sergeantHostSend" in command_center_js
    assert "window.addEventListener('message'" in command_center_js
    assert "Commander → Mission → Officers → Weapon Manifest → Evidence → Verification → Commander Verdict → Audit Trail" in command_center_js
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
