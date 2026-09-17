"""Generate and verify SwirUI progress SVGs from the authoritative ROADMAP.md.

The established weighted model is preserved: verified work through 0.3 contributes the
41% baseline recorded before 0.4 began, then each verified 0.4 widget group contributes
one percentage point. Release readiness is intentionally not inferred from project progress.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = ROOT / "ROADMAP.md"
CARD_PATH = ROOT / "assets" / "readme" / "progress-card.svg"
MINI_PATH = ROOT / "assets" / "readme" / "progress-mini.svg"
TEMPLATE_PATH = ROOT / "assets" / "readme" / "progress-template.svg"

PROJECT = "SwirUI"
CURRENT_SCOPE = "0.4 Alpha — Core Widgets"
BASE_PROJECT_PERCENT = Decimal("41")
VERIFIED_GROUP_WEIGHT = Decimal("1")
EXPECTED_GROUPS = 15
COUNTER_LABEL = "widget groups verified"

OVERALL_RE = re.compile(r"\*\*Overall completion: (?P<percent>\d+(?:\.\d+)?)%\*\*")
CHECKBOX_RE = re.compile(r"^- \[(?P<state>[ xX])\] ", re.MULTILINE)

CARD_TRACK_WIDTH = Decimal("1100")
MINI_TRACK_WIDTH = Decimal("700")


@dataclass(frozen=True)
class ProgressData:
    project: str
    scope: str
    status: str
    percentage: Decimal | None
    completed: int | None
    total: int | None
    counter_label: str

    @property
    def percentage_text(self) -> str:
        if self.percentage is None:
            return "N/A"
        return f"{self.percentage.quantize(Decimal('0.1'))}%"

    @property
    def counter_text(self) -> str:
        if self.completed is None or self.total is None:
            return f"N/A {self.counter_label}"
        return f"{self.completed} / {self.total} {self.counter_label}"


def _section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    start = markdown.find(marker)
    if start < 0:
        raise ValueError(f"Missing roadmap section: {heading}")
    body_start = start + len(marker)
    next_heading = markdown.find("\n## ", body_start)
    return markdown[body_start:] if next_heading < 0 else markdown[body_start:next_heading]


def parse_progress(markdown: str) -> ProgressData:
    section = _section(markdown, CURRENT_SCOPE)
    states = [match.group("state").lower() for match in CHECKBOX_RE.finditer(section)]
    if not states:
        raise ValueError(f"No checklist items found for scope: {CURRENT_SCOPE}")
    if len(states) != EXPECTED_GROUPS:
        raise ValueError(
            f"Expected {EXPECTED_GROUPS} {CURRENT_SCOPE} groups, found {len(states)}"
        )

    completed = sum(state == "x" for state in states)
    computed = BASE_PROJECT_PERCENT + VERIFIED_GROUP_WEIGHT * completed
    if not Decimal("0") <= computed <= Decimal("100"):
        raise ValueError(f"Computed project percentage is out of bounds: {computed}")

    overall_match = OVERALL_RE.search(markdown)
    if overall_match is None:
        raise ValueError("Missing authoritative Overall completion percentage")
    documented = Decimal(overall_match.group("percent"))
    if documented != computed:
        raise ValueError(
            "ROADMAP percentage is stale or contradictory: "
            f"documented={documented} computed={computed}"
        )

    status = "COMPLETE" if completed == len(states) else "IN PROGRESS"
    return ProgressData(
        project=PROJECT,
        scope=CURRENT_SCOPE,
        status=status,
        percentage=computed,
        completed=completed,
        total=len(states),
        counter_label=COUNTER_LABEL,
    )


def _fill_width(track_width: Decimal, percentage: Decimal | None) -> Decimal:
    if percentage is None:
        return Decimal("0")
    fraction = min(max(percentage / Decimal("100"), Decimal("0")), Decimal("1"))
    return track_width * fraction


def _fmt(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _scope_lines(scope: str, width: int) -> list[str]:
    return textwrap.wrap(
        scope,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [scope]


def _svg_open(width: int, height: int) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="title desc">'
    )


def render_card(data: ProgressData) -> str:
    scope_lines = _scope_lines(data.scope, 62)
    height = 180 if len(scope_lines) == 1 else 210
    track_y = 116 if height == 180 else 146
    label_y = 155 if height == 180 else 185
    fill_width = _fill_width(CARD_TRACK_WIDTH, data.percentage)
    fill = ""
    if fill_width > 0:
        fill = (
            f'<rect data-role="progress-fill" x="50" y="{track_y}" '
            f'width="{_fmt(fill_width)}" height="18" rx="9" '
            'fill="url(#progressGradient)" filter="url(#softGlow)"/>'
        )

    scope_svg = "\n".join(
        f'<text x="50" y="{76 + index * 24}" class="scope">{_escape(line)}</text>'
        for index, line in enumerate(scope_lines)
    )
    description = (
        f"{data.project} project progress for {data.scope}: {data.percentage_text}, "
        f"status {data.status}, {data.counter_text}."
    )
    lines = [
        _svg_open(1200, height),
        f'  <title id="title">SwirUI project progress — {data.percentage_text}</title>',
        f'  <desc id="desc">{_escape(description)}</desc>',
        "  <defs>",
        '    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0" stop-color="#02050A"/>',
        '      <stop offset="1" stop-color="#07111C"/>',
        "    </linearGradient>",
        '    <linearGradient id="progressGradient" x1="0" y1="0" x2="1" y2="0">',
        '      <stop offset="0" stop-color="#0088FF"/>',
        '      <stop offset="1" stop-color="#62E5FF"/>',
        "    </linearGradient>",
        '    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">',
        (
            '      <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#0B3550" '
            'stroke-width="1" opacity="0.24"/>'
        ),
        "    </pattern>",
        '    <filter id="softGlow" x="-20%" y="-100%" width="140%" height="300%">',
        '      <feGaussianBlur stdDeviation="5" result="blur"/>',
        "      <feMerge>",
        '        <feMergeNode in="blur"/>',
        '        <feMergeNode in="SourceGraphic"/>',
        "      </feMerge>",
        "    </filter>",
        "    <style>",
        "      .project { fill:#F4FAFF; font:700 24px 'Segoe UI',Arial,sans-serif; }",
        "      .scope { fill:#8DA8B8; font:500 17px 'Segoe UI',Arial,sans-serif; }",
        "      .percent { fill:#62E5FF; font:800 34px 'Segoe UI',Arial,sans-serif; }",
        (
            "      .meta { fill:#8DA8B8; font:600 14px 'Segoe UI',Arial,sans-serif; "
            "letter-spacing:.5px; }"
        ),
        "      .counter { fill:#F4FAFF; font:600 14px 'Segoe UI',Arial,sans-serif; }",
        "    </style>",
        "  </defs>",
        (
            f'  <rect x="1" y="1" width="1198" height="{height - 2}" rx="22" '
            'fill="url(#surface)" stroke="#164D6B" stroke-width="2"/>'
        ),
        (
            f'  <rect x="2" y="2" width="1196" height="{height - 4}" rx="21" '
            'fill="url(#grid)" opacity="0.65"/>'
        ),
        '  <path d="M 28 24 H 180" stroke="#0088FF" stroke-width="3" opacity="0.75"/>',
        (
            f'  <path d="M 1020 {height - 24} H 1170" stroke="#62E5FF" '
            'stroke-width="3" opacity="0.55"/>'
        ),
        f'  <text x="50" y="48" class="project">{_escape(data.project)}</text>',
        scope_svg,
        (
            f'  <text x="1150" y="50" text-anchor="end" class="percent">'
            f"{data.percentage_text}</text>"
        ),
        (
            '  <text x="1150" y="78" text-anchor="end" class="meta">'
            f"PROJECT PROGRESS • {data.status}</text>"
        ),
        (
            f'  <rect data-role="progress-track" x="50" y="{track_y}" width="1100" '
            'height="18" rx="9" fill="#07111C" stroke="#164D6B" stroke-width="1"/>'
        ),
        f"  {fill}",
        (
            f'  <text x="50" y="{label_y}" class="counter">'
            f"{_escape(data.counter_text)}</text>"
        ),
        (
            f'  <text x="1150" y="{label_y}" text-anchor="end" class="meta">'
            "SOURCE: ROADMAP.md • WEIGHTED VERIFIED SCOPE</text>"
        ),
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def render_mini(data: ProgressData) -> str:
    scope_lines = _scope_lines(data.scope, 46)
    height = 72 if len(scope_lines) == 1 else 92
    track_y = 42 if height == 72 else 62
    fill_width = _fill_width(MINI_TRACK_WIDTH, data.percentage)
    fill = ""
    if fill_width > 0:
        fill = (
            f'<rect data-role="progress-fill" x="170" y="{track_y}" '
            f'width="{_fmt(fill_width)}" height="10" rx="5" '
            'fill="url(#progressGradient)"/>'
        )
    scope_svg = "\n".join(
        f'<text x="18" y="{24 + index * 18}" class="scope">{_escape(line)}</text>'
        for index, line in enumerate(scope_lines)
    )
    description = (
        f"{data.project} {data.scope}: {data.percentage_text}, "
        f"{data.status}, {data.counter_text}."
    )
    lines = [
        _svg_open(900, height),
        f'  <title id="title">SwirUI roadmap progress — {data.percentage_text}</title>',
        f'  <desc id="desc">{_escape(description)}</desc>',
        "  <defs>",
        '    <linearGradient id="progressGradient" x1="0" y1="0" x2="1" y2="0">',
        '      <stop offset="0" stop-color="#0088FF"/>',
        '      <stop offset="1" stop-color="#62E5FF"/>',
        "    </linearGradient>",
        "    <style>",
        "      .scope { fill:#F4FAFF; font:600 13px 'Segoe UI',Arial,sans-serif; }",
        "      .meta { fill:#8DA8B8; font:600 11px 'Segoe UI',Arial,sans-serif; }",
        "      .percent { fill:#62E5FF; font:800 18px 'Segoe UI',Arial,sans-serif; }",
        "    </style>",
        "  </defs>",
        (
            f'  <rect x="1" y="1" width="898" height="{height - 2}" rx="14" '
            'fill="#02050A" stroke="#164D6B" stroke-width="2"/>'
        ),
        scope_svg,
        (
            f'  <text x="882" y="24" text-anchor="end" class="percent">'
            f"{data.percentage_text}</text>"
        ),
        (
            f'  <text x="882" y="{height - 12}" text-anchor="end" class="meta">'
            f"{_escape(data.status)} • {_escape(data.counter_text)}</text>"
        ),
        (
            f'  <rect data-role="progress-track" x="170" y="{track_y}" width="700" '
            'height="10" rx="5" fill="#07111C" stroke="#164D6B" stroke-width="1"/>'
        ),
        f"  {fill}",
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def render_template() -> str:
    lines = [
        _svg_open(1200, 180),
        '  <title id="title">SWIR progress card template — not project data</title>',
        (
            '  <desc id="desc">Reusable SWIR progress SVG template. '
            "This file contains no live project percentage.</desc>"
        ),
        "  <defs>",
        '    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0" stop-color="#02050A"/>',
        '      <stop offset="1" stop-color="#07111C"/>',
        "    </linearGradient>",
        "    <style>",
        "      .project { fill:#F4FAFF; font:700 24px 'Segoe UI',Arial,sans-serif; }",
        "      .scope { fill:#8DA8B8; font:500 17px 'Segoe UI',Arial,sans-serif; }",
        "      .percent { fill:#62E5FF; font:800 34px 'Segoe UI',Arial,sans-serif; }",
        "      .meta { fill:#8DA8B8; font:600 14px 'Segoe UI',Arial,sans-serif; }",
        "    </style>",
        "  </defs>",
        (
            '  <rect x="1" y="1" width="1198" height="178" rx="22" '
            'fill="url(#surface)" stroke="#164D6B" stroke-width="2"/>'
        ),
        '  <text x="50" y="48" class="project">PROJECT NAME</text>',
        '  <text x="50" y="78" class="scope">MEASURED SCOPE</text>',
        '  <text x="1150" y="50" text-anchor="end" class="percent">N/A</text>',
        (
            '  <text x="1150" y="78" text-anchor="end" class="meta">'
            "TEMPLATE / NOT PROJECT DATA</text>"
        ),
        (
            '  <rect x="50" y="116" width="1100" height="18" rx="9" '
            'fill="#07111C" stroke="#164D6B" stroke-width="1"/>'
        ),
        (
            '  <text x="50" y="155" class="meta">'
            "COUNTER: N/A • GENERATE WITH tools/progress_svg.py</text>"
        ),
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def _validate_xml(name: str, content: str) -> None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"{name} is not valid XML: {exc}") from exc
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError(f"{name} root is not SVG")
    view_box = root.attrib.get("viewBox", "").split()
    if len(view_box) != 4:
        raise ValueError(f"{name} must have a four-number viewBox")
    for value in view_box:
        float(value)


def expected_outputs(roadmap_text: str) -> dict[Path, str]:
    data = parse_progress(roadmap_text)
    outputs = {
        CARD_PATH: render_card(data),
        MINI_PATH: render_mini(data),
        TEMPLATE_PATH: render_template(),
    }
    for path, content in outputs.items():
        _validate_xml(path.name, content)
    return outputs


def check_outputs(root: Path = ROOT) -> list[str]:
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    expected = expected_outputs(roadmap)
    errors: list[str] = []
    for canonical_path, expected_content in expected.items():
        path = root / canonical_path.relative_to(ROOT)
        if not path.exists():
            errors.append(f"missing {path.relative_to(root)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected_content:
            errors.append(f"stale {path.relative_to(root)}")
            continue
        try:
            _validate_xml(path.name, actual)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def write_outputs() -> None:
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    outputs = expected_outputs(roadmap)
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic SwirUI progress SVG assets."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed SVG assets are stale or contradictory.",
    )
    args = parser.parse_args(argv)

    if args.check:
        errors = check_outputs()
        if errors:
            for error in errors:
                print(f"progress-svg: {error}", file=sys.stderr)
            return 1
        print("progress-svg: assets are current and valid")
        return 0

    write_outputs()
    print(
        "progress-svg: regenerated progress-card.svg, progress-mini.svg "
        "and progress-template.svg"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
