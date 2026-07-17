#!/usr/bin/env python3
"""Apply the final quoted-inline-workflow scalar correction."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "main_review" / "offline_investigation.py"
    text = path.read_text(encoding="utf-8")
    old = "        if inline and inline not in literal_markers | folded_markers:\n            command_lines.append(inline)\n"
    new = "        if inline and inline not in literal_markers | folded_markers:\n            command_lines.append(_clean_yaml_scalar(inline))\n"
    if old in text:
        text = text.replace(old, new, 1)
    if "command_lines.append(_clean_yaml_scalar(inline))" not in text:
        raise RuntimeError("quoted inline workflow command normalization marker missing")
    path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
