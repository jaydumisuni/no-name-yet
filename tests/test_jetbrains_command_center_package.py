from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_jetbrains_plugin_bundles_shared_command_center() -> None:
    build = (ROOT / "adapters" / "jetbrains" / "build.gradle.kts").read_text(encoding="utf-8")
    props = (ROOT / "adapters" / "jetbrains" / "gradle.properties").read_text(encoding="utf-8")
    panel = (
        ROOT
        / "adapters"
        / "jetbrains"
        / "src"
        / "main"
        / "kotlin"
        / "com"
        / "thetechguyds"
        / "sergeant"
        / "SergeantToolWindowFactory.kt"
    ).read_text(encoding="utf-8")
    runner = (
        ROOT
        / "adapters"
        / "jetbrains"
        / "src"
        / "main"
        / "kotlin"
        / "com"
        / "thetechguyds"
        / "sergeant"
        / "SergeantRunner.kt"
    ).read_text(encoding="utf-8")

    assert 'resources.srcDir("../../resources")' in build
    assert "pluginVersion=0.3.2-preview" in props
    assert "platformVersion=2025.2.6.2" in props
    assert "JBCefBrowser" in panel
    assert "JBCefJSQuery" in panel
    assert "sergeant-command-center-v2.html" in panel
    assert "sergeantHostSend" in panel
    assert "window.postMessage" in panel
    assert "SergeantFallbackPanel" in panel
    assert "copyLastReport" in panel
    assert "exportLastReport" in panel

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
