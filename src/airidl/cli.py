"""Command-line entry point for Airi-DL."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import cast

from airidl import __version__
from airidl.doctor import Profile, collect_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="airidl")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect host capabilities without changing them")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    doctor.add_argument(
        "--profile",
        choices=("auto", "macos-dev", "portable-ci", "ubuntu-cuda"),
        default="auto",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    profile: Profile = args.profile
    report = collect_report(profile)
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Airi-DL {__version__} | {report['profile']} | {report['overall']}")
        checks = cast(list[dict[str, object]], report["checks"])
        for item in checks:
            status = str(item["status"])
            actual = item["actual"] or item["expected"]
            print(f"[{status:>4}] {item['name']}: {actual}")
    return 0 if report["overall"] == "pass" else 3
