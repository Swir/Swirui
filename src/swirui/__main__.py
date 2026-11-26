"""Installed-package entry point: python -m swirui."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from functools import partial

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
    preview = commands.add_parser("preview-theme", help="Try a saved theme package in a window")
    preview.add_argument("file", help="Path to a SwirUI theme JSON file")
    display = preview.add_mutually_exclusive_group()
    display.add_argument("--variant", action="append", metavar="KEY",
                         help="Show this variant. Repeat once to compare two in the given order.")
    display.add_argument("--list-variants", action="store_true", help="List keys and the default")
    preview.add_argument("--smoke-test", action="store_true", help="Render and close the preview")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "doctor":
        report = installation_report()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"SwirUI {report['version']} / Python {report['python']}")
            print(f"{report['platform']} / {report['architecture']}")
            print(report["message"])
        return 0 if report["ready"] else 1
    if args.command == "preview-theme":
        from .studio_comparison import AppearanceComparison, run_package_preview
        from .theme_package import ThemePackage

        if args.list_variants and args.smoke_test:
            preview.error("choose either --list-variants or --smoke-test")
        try:
            package = ThemePackage.load(args.file)
            if args.list_variants:
                for key in package.themes:
                    print(key + (" (default)" if key == package.default_theme else ""))
                return 0
            if args.variant:
                keys = tuple(args.variant)
            else:
                others = [key for key in package.themes if key != package.default_theme]
                keys = (package.default_theme, *others[:1])
            root = AppearanceComparison(package, "Project settings", variants=keys)
        except (OSError, ValueError) as error:
            print(f"Could not preview {args.file!r}: {error}", file=sys.stderr)
            return 1
        start = partial(run_package_preview, root, smoke_test=args.smoke_test)
    elif args.command == "demo":
        from .demo import run
        start = partial(run, smoke_test=args.smoke_test)
    else:
        from .studio_suite import run
        start = partial(run, smoke_test=args.smoke_test)

    report = installation_report()
    if not report["ready"]:
        print(report["message"], file=sys.stderr)
        return 1
    try:
        return start()
    except (RuntimeError, OSError, ImportError) as error:
        print(f"SwirUI could not start its native renderer: {error}", file=sys.stderr)
        print("Check your graphics driver and run python -m swirui doctor.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
