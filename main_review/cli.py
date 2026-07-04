"""Command line entrypoint for Main Review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scanner import scan_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main-review")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Build a static repository intelligence packet.")
    scan_parser.add_argument("path", nargs="?", default=".", help="Repository path to scan.")
    scan_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        insight = scan_repository(Path(args.path))
        indent = 2 if args.pretty else None
        print(json.dumps(insight.to_dict(), indent=indent, sort_keys=True))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
