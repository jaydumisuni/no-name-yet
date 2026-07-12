from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JETBRAINS = ROOT / "adapters" / "jetbrains"


def test_jetbrains_plugin_bundles_shared_command_center() -> None:
    build = (JETBRAINS / "build.gradle.kts").read_text(encoding="utf-8")
    properties = (JETBRAINS / "gradle.properties").read_text(encoding="utf-8")
    plugin_xml = (JETBRAINS / "src" / "main" / "resources" / "META-INF" / "plugin.xml").read_text(encoding="utf-8")
    tool_window = (
        JETBRAINS
        / "src"
        / "main"
        / "kotlin"
        / "com"
        / "thetechguyds"
        / "sergeant"
        / "SergeantToolWindowFactory.kt"
    ).read_text(encoding="utf-8")
    runner = (
        JETBRAINS
        / "src"
        / "main"
        / "kotlin"
        / "com"
        / "thetechguyds"
        / "sergeant"
        / "SergeantRunner.kt"
    ).read_text(encoding="utf-8")

    assert 'resources.srcDir("../../resources")' in build
    assert "pluginVersion=0.3.2-preview" in properties
    assert "complete Command Center" in plugin_xml
    assert "JBCefBrowser" in tool_window
    assert "JBCefJSQuery" in tool_window
    assert "sergeant-command-center-v2.html" in tool_window
    assert "sergeant-command-center-v2.css" in tool_window
    assert "sergeant-command-center-v2-responsive.css" in tool_window
    assert "sergeant-command-center-v2.js" in tool_window
    assert "sergeantHostSend" in tool_window
    assert "sergeantState" in tool_window
    assert "saveSettings" in tool_window
    assert "copyLastReport" in tool_window
    assert "exportLastReport" in tool_window
    assert "SergeantFallbackPanel" in tool_window
    assert "Content-Security-Policy" in tool_window
    assert "parseMissionContext" in tool_window
    assert '"missionContext" to missionContext' in tool_window
    assert '"currentMission" to currentMission' in tool_window
    assert "loadHistory" in tool_window
    assert "saveHistory" in tool_window
    assert "sergeant.commandCenter.history" in tool_window

    for action in [
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
        assert f'"{action}"' in runner


def test_shared_ui_contains_no_fake_runtime_generator() -> None:
    script = (ROOT / "resources" / "sergeant-command-center-v2.js").read_text(encoding="utf-8")
    html = (ROOT / "resources" / "sergeant-command-center-v2.html").read_text(encoding="utf-8")

    assert "Math.random" not in script
    assert "setInterval(() => step" not in script
    assert "Standalone preview mode" in script
    assert "No runtime evidence yet" in html
    assert "AWAITING MISSION" in script
    assert "selectedMission" in script
    assert "escapeHtml" in script
