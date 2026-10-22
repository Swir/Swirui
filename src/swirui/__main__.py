"""Installed-package entry point: python -m swirui."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__
from .diagnostics import installation_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SwirUI desktop beta")
    parser.add_argument("--version", action="version", version=f"SwirUI {__version__}")
    commands = parser.add_subparsers(dest="command")
    doctor = commands.add_parser("doctor", help="Check installation without opening a window")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    demo = commands.add_parser("demo", help="Open the interactive material and theme gallery")
    demo.add_argument(
        "--smoke-test",
        action="store_true",
        help="Render, verify and close the gallery",
    )
    studio = commands.add_parser(
        "studio",
        help="Open the integrated preview, code, hierarchy and inspector workspace",
    )
    studio.add_argument(
        "--smoke-test",
        action="store_true",
        help="Render, verify and close the integrated Studio",
    )
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    report = installation_report()
    if args.command == "doctor":
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"SwirUI {report['version']} / Python {report['python']}")
            print(f"{report['platform']} / {report['architecture']}")
            print(report["message"])
        return 0 if report["ready"] else 1
    if not report["ready"]:
        print(report["message"], file=sys.stderr)
        return 1
    if args.command == "demo":
        from .demo import run
    else:
        from .studio_suite import run

    try:
        return run(smoke_test=args.smoke_test)
    except (RuntimeError, OSError, ImportError) as error:
        print(f"SwirUI could not start its native renderer: {error}", file=sys.stderr)
        print("Check your graphics driver and run python -m swirui doctor.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
