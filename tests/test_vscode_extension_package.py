from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vscode_extension_manifest_installs_sergeant_commands() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    commands = {item["command"] for item in package["contributes"]["commands"]}

    assert package["displayName"] == "Sergeant"
    assert package["icon"] == "resources/srg-logo-and-icon.png"
    assert package["main"] == "./vscode-extension.js"
    assert "sergeant.reviewWorkspace" in commands
    assert "sergeant.ideBenchContract" in commands
    assert (ROOT / package["icon"]).is_file()


def test_vscode_extension_runtime_uses_bundled_launcher() -> None:
    runtime = (ROOT / "vscode-extension.js").read_text(encoding="utf-8")

    assert 'path.join(__dirname, "sergeant.py")' in runtime
    assert '"review"' in runtime
    assert '"ide-bench-contract"' in runtime
