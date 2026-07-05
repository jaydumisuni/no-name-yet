from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_ASSET = "resources/srg-logo-and-icon.png"


def test_vscode_launches_sergeant_launcher_with_icon_asset() -> None:
    payload = json.loads((ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
    configs = {config["name"]: config for config in payload["configurations"]}

    ide_bench = configs["Sergeant: IDE Bench Contract"]
    review = configs["Sergeant: Review Workspace"]

    assert ide_bench["program"] == "${workspaceFolder}/sergeant.py"
    assert ide_bench["args"] == ["ide-bench-contract", "--pretty"]
    assert ide_bench["env"]["SERGEANT_ICON_ASSET"] == ICON_ASSET
    assert review["program"] == "${workspaceFolder}/sergeant.py"
    assert review["args"] == ["review", ".", "--pretty"]
    assert review["env"]["SERGEANT_ICON_ASSET"] == ICON_ASSET


def test_pycharm_run_configs_launch_sergeant_with_icon_asset() -> None:
    config_dir = ROOT / ".idea" / "runConfigurations"
    configs = {
        path.name: ET.parse(path).getroot().find("configuration")
        for path in config_dir.glob("Sergeant_*.xml")
    }

    assert configs["Sergeant_IDE_Bench.xml"] is not None
    assert configs["Sergeant_Review_Workspace.xml"] is not None

    ide_bench = configs["Sergeant_IDE_Bench.xml"]
    review = configs["Sergeant_Review_Workspace.xml"]

    assert ide_bench.find("./option[@name='SCRIPT_NAME']").attrib["value"] == "$PROJECT_DIR$/sergeant.py"
    assert ide_bench.find("./option[@name='PARAMETERS']").attrib["value"] == "ide-bench-contract --pretty"
    assert ide_bench.find("./envs/env[@name='SERGEANT_ICON_ASSET']").attrib["value"] == ICON_ASSET
    assert review.find("./option[@name='SCRIPT_NAME']").attrib["value"] == "$PROJECT_DIR$/sergeant.py"
    assert review.find("./option[@name='PARAMETERS']").attrib["value"] == "review . --pretty"
    assert review.find("./envs/env[@name='SERGEANT_ICON_ASSET']").attrib["value"] == ICON_ASSET


def test_readme_and_icon_assets_exist() -> None:
    assert (ROOT / "resources" / "readme-top-image.png").is_file()
    assert (ROOT / ICON_ASSET).is_file()
