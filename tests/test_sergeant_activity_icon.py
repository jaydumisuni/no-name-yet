from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def test_vscode_activity_icon_is_the_three_stripe_rank_mark() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    icon_path = package["contributes"]["viewsContainers"]["activitybar"][0]["icon"]

    assert icon_path == "resources/sergeant-activity.svg"

    icon = ROOT / icon_path
    source = icon.read_text(encoding="utf-8")
    root = ET.fromstring(source)
    paths = root.findall(".//{http://www.w3.org/2000/svg}path")

    assert root.attrib["aria-label"] == "Sergeant three-stripe rank mark"
    assert len(paths) == 3
    assert [path.attrib["d"] for path in paths] == [
        "M4 8 12 4l8 4",
        "M4 13 12 9l8 4",
        "M4 18 12 14l8 4",
    ]
    assert "shield" not in source.lower()
    assert "linearGradient" not in source
    assert 'stroke="currentColor"' in source
