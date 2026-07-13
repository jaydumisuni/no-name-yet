from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JETBRAINS_SOURCE = (
    ROOT
    / "adapters"
    / "jetbrains"
    / "src"
    / "main"
    / "kotlin"
    / "com"
    / "thetechguyds"
    / "sergeant"
)


def test_jetbrains_plugin_bundles_shared_command_center() -> None:
    build = (ROOT / "adapters" / "jetbrains" / "build.gradle.kts").read_text(encoding="utf-8")
    props = (ROOT / "adapters" / "jetbrains" / "gradle.properties").read_text(encoding="utf-8")
    panel = (JETBRAINS_SOURCE / "SergeantToolWindowFactory.kt").read_text(encoding="utf-8")
    runner = (JETBRAINS_SOURCE / "SergeantRunner.kt").read_text(encoding="utf-8")
    gate = (JETBRAINS_SOURCE / "SergeantMissionGate.kt").read_text(encoding="utf-8")

    assert 'resources.srcDir("../../resources")' in build
    assert "pluginVersion=0.4.0-preview" in props
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

    assert 'listOf("pr-review", root, "--pretty")' in runner
    assert 'listOf("pr-review", root, "--files", it, "--pretty")' in runner
    assert "PropertiesComponent" in runner
    assert "applySemanticEnvironment" in runner
    for environment_name in [
        "SERGEANT_LLM_ENABLED",
        "SERGEANT_LLM_POLICY",
        "SERGEANT_LLM_PROVIDER",
        "SERGEANT_LLM_BASE_URL",
        "SERGEANT_LLM_MODEL",
        "SERGEANT_LLM_PROTOCOL",
        "SERGEANT_LLM_COUNCIL",
    ]:
        assert environment_name in runner

    assert "semanticSettingKeys" in panel
    assert "saveSemanticSettings" in panel
    assert "semanticSettings" in panel
    for property_name in [
        "sergeant.llm.policy",
        "sergeant.llm.provider",
        "sergeant.llm.baseUrl",
        "sergeant.llm.model",
        "sergeant.llm.protocol",
        "sergeant.llm.council",
    ]:
        assert property_name in panel

    assert "SergeantMissionGate.tryAcquire(project)" in runner
    assert "SergeantMissionGate.release(project)" in runner
    assert "finally" in runner
    assert "ConcurrentHashMap.newKeySet<Project>()" in gate
    assert "fun tryAcquire(project: Project)" in gate
    assert "fun release(project: Project)" in gate
    assert "A Sergeant mission is already running for this project" in runner
