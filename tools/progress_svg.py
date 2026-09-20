"""Generate and verify PyPI-safe ASCII progress blocks for SwirUI.

The filename is retained for CI compatibility. SwirUI intentionally uses text-only
progress presentation in README/PyPI-facing documentation.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = ROOT / "ROADMAP.md"
README_PATH = ROOT / "README.md"

PROJECT = "SwirUI"
CURRENT_SCOPE = "0.5 Alpha — Layout Engine"
BASE_PROJECT_PERCENT = Decimal("56")
VERIFIED_GROUP_WEIGHT = Decimal("1")
EXPECTED_GROUPS = 12
COUNTER_LABEL = "layout groups verified"
ASCII_WIDTH = 20

README_START = "<!-- SWIR-ASCII-PROGRESS:START -->"
README_END = "<!-- SWIR-ASCII-PROGRESS:END -->"
ROADMAP_START = "<!-- SWIR-ROADMAP-ASCII-PROGRESS:START -->"
ROADMAP_END = "<!-- SWIR-ROADMAP-ASCII-PROGRESS:END -->"

OVERALL_RE = re.compile(r"\*\*Overall completion: (?P<percent>\d+(?:\.\d+)?)%\*\*")
CHECKBOX_RE = re.compile(r"^- \[(?P<state>[ xX])\] ", re.MULTILINE)
PROGRESS_SVG_LINE_RE = re.compile(
    r"^\s*<img[^>\n]*assets/readme/progress-(?:card|mini)\.svg[^>\n]*>\s*$\n?",
    re.MULTILINE,
)


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
        return "N/A" if self.percentage is None else f"{self.percentage.quantize(Decimal('0.1'))}%"

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
        raise ValueError(f"Expected {EXPECTED_GROUPS} {CURRENT_SCOPE} groups, found {len(states)}")

    completed = sum(state == "x" for state in states)
    computed = BASE_PROJECT_PERCENT + VERIFIED_GROUP_WEIGHT * completed
    documented_match = OVERALL_RE.search(markdown)
    if documented_match is None:
        raise ValueError("Missing authoritative Overall completion percentage")
    documented = Decimal(documented_match.group("percent"))
    if documented != computed:
        raise ValueError(
            f"ROADMAP percentage is stale or contradictory: documented={documented} computed={computed}"
        )

    return ProgressData(
        project=PROJECT,
        scope=CURRENT_SCOPE,
        status="COMPLETE" if completed == len(states) else "IN PROGRESS",
        percentage=computed,
        completed=completed,
        total=len(states),
        counter_label=COUNTER_LABEL,
    )


def render_ascii(data: ProgressData, *, start: str = README_START, end: str = README_END) -> str:
    if data.percentage is None:
        body = "Progress: N/A\n" + data.counter_text
    else:
        filled = int((data.percentage / Decimal("100") * ASCII_WIDTH) + Decimal("0.5"))
        filled = max(0, min(ASCII_WIDTH, filled))
        bar = "#" * filled + "-" * (ASCII_WIDTH - filled)
        body = f"[{bar}] {data.percentage_text}\n{data.counter_text}"
    return f"{start}\n```text\n{body}\n```\n{end}"


def _replace_block(text: str, *, start: str, end: str, block: str, anchor: str) -> str:
    starts = text.count(start)
    ends = text.count(end)
    if starts != ends or starts > 1:
        raise ValueError(f"Malformed ASCII progress markers: {start}")
    if starts == 1:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        return pattern.sub(block, text, count=1)
    if anchor not in text:
        raise ValueError(f"Missing insertion anchor: {anchor.strip()}")
    return text.replace(anchor, anchor + "\n" + block + "\n", 1)


def expected_documents(readme: str, roadmap: str) -> tuple[str, str]:
    data = parse_progress(roadmap)
    readme = PROGRESS_SVG_LINE_RE.sub("", readme)
    roadmap = PROGRESS_SVG_LINE_RE.sub("", roadmap)
    readme = _replace_block(
        readme,
        start=README_START,
        end=README_END,
        block=render_ascii(data),
        anchor="## Project Status\n",
    )
    roadmap = _replace_block(
        roadmap,
        start=ROADMAP_START,
        end=ROADMAP_END,
        block=render_ascii(data, start=ROADMAP_START, end=ROADMAP_END),
        anchor="## Project progress\n",
    )
    return readme, roadmap


def check_outputs(root: Path = ROOT) -> list[str]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    expected_readme, expected_roadmap = expected_documents(readme, roadmap)
    errors: list[str] = []
    if readme != expected_readme:
        errors.append("stale README.md ASCII progress")
    if roadmap != expected_roadmap:
        errors.append("stale ROADMAP.md ASCII progress")
    for name, text in (("README.md", readme), ("ROADMAP.md", roadmap)):
        if "assets/readme/progress-card.svg" in text or "assets/readme/progress-mini.svg" in text:
            errors.append(f"{name} embeds graphical progress")
    return errors


def write_outputs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    expected_readme, expected_roadmap = expected_documents(readme, roadmap)
    README_PATH.write_text(expected_readme, encoding="utf-8", newline="\n")
    ROADMAP_PATH.write_text(expected_roadmap, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic SwirUI ASCII progress.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        errors = check_outputs()
        if errors:
            for error in errors:
                print(f"progress-ascii: {error}", file=sys.stderr)
            return 1
        print("progress-ascii: README and ROADMAP are current")
        return 0
    write_outputs()
    print("progress-ascii: updated README.md and ROADMAP.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
