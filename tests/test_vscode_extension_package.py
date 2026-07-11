from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vscode_extension_manifest_installs_sergeant_commands() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    commands = {item["command"] for item in package["contributes"]["commands"]}
    containers = package["contributes"]["viewsContainers"]["activitybar"]

    assert "activationEvents" not in package
    assert package["displayName"] == "Sergeant"
    assert package["icon"] == "resources/srg-logo-and-icon.png"
    assert package["main"] == "./vscode-extension.js"
    assert containers[0]["id"] == "sergeant"
    assert containers[0]["title"] == "Sergeant"
    assert containers[0]["icon"] == "resources/sergeant-activity.svg"
    assert (ROOT / containers[0]["icon"]).is_file()
    assert "sergeant.reviewWorkspace" in commands
    assert "sergeant.appReviewWorkspace" in commands
    assert "sergeant.reviewCurrentFile" in commands
    assert "sergeant.reviewChangedFiles" in commands
    assert "sergeant.v2Mission" in commands
    assert "sergeant.proofSuite" in commands
    assert "sergeant.finalProof" in commands
    assert "sergeant.verifyStandard" in commands
    assert "sergeant.battleTests" in commands
    assert "sergeant.ideBenchContract" in commands
    assert "sergeant.openLastReport" in commands
    assert "sergeant.copyLastReport" in commands
    assert "sergeant.exportLastReport" in commands
    assert (ROOT / package["icon"]).is_file()


def test_vscode_extension_runtime_uses_bundled_launcher() -> None:
    runtime = (ROOT / "vscode-extension.js").read_text(encoding="utf-8")

    assert 'path.join(__dirname, "sergeant.py")' in runtime
    assert "registerWebviewViewProvider" in runtime
    assert "SergeantCommandCenterProvider" in runtime
    assert "ACTIONS" in runtime
    assert "SGT Command Center" in runtime
    assert "Mission Planner" in runtime
    assert "Review workspace evidence." in runtime
    assert "Evidence Locker" in runtime
    assert "Review Doctrine" in runtime
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in runtime
    assert "showResultPanel" in runtime
    assert "renderResultHtml" in runtime
    assert "Required Actions" in runtime
    assert "Top Findings" in runtime
    assert "Raw Evidence" in runtime
    assert "createWebviewPanel" in runtime
    assert '"review"' in runtime
    assert '"app-review"' in runtime
    assert '"changed_files"' in runtime
    assert '"v2-mission"' in runtime
    assert '"proof-suite"' in runtime
    assert '"final-proof"' in runtime
    assert '"verify-standard"' in runtime
    assert '"battle-tests"' in runtime
    assert '"ide-bench-contract"' in runtime


def test_command_center_visible_controls_are_wired() -> None:
    runtime = (ROOT / "vscode-extension.js").read_text(encoding="utf-8")

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
        assert f'id: "{action_id}"' in runtime
        assert f'data-run="${{escapeHtml(action.id)}}"' in runtime or f'data-run="{action_id}"' in runtime

    for control_id, message_type in {
        "launchMission": "run",
        "openLast": "openLast",
        "copyLast": "copyLast",
        "exportLast": "exportLast",
        "refresh": "refresh",
    }.items():
        assert f'id="{control_id}"' in runtime
        assert f"type:'{message_type}'" in runtime or f'type: "{message_type}"' in runtime

    assert "onDidReceiveMessage" in runtime
    assert "handleMessage" in runtime
    assert "copyLastReport" in runtime
    assert "exportLastReport" in runtime
