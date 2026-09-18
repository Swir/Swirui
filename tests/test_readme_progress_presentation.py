from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "ROADMAP.md"
CARD = "assets/readme/progress-card.svg"
MINI = "assets/readme/progress-mini.svg"
TEMPLATE = "assets/readme/progress-template.svg"

_LEGACY_METER = re.compile(r"(?:[█▓▒░■□▰▱]{4,}|\[[#=\-]{5,}\])")
_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)


def _presentation_text(path: Path) -> str:
    """Return maintained prose while ignoring command examples and directory trees."""

    return _FENCED_CODE.sub("", path.read_text(encoding="utf-8"))


def test_progress_graphics_have_one_authoritative_embedding_per_dashboard() -> None:
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert readme.startswith("<!-- SWIR-README-STANDARD:v2 -->")
    assert "## 🔎 Search Keywords" in readme
    assert readme.count(CARD) == 1
    assert MINI not in readme
    assert TEMPLATE not in readme

    assert roadmap.count(MINI) == 1
    assert CARD not in roadmap
    assert TEMPLATE not in roadmap


def test_live_dashboards_do_not_restore_legacy_character_progress_meters() -> None:
    for path in (README, ROADMAP):
        maintained_prose = _presentation_text(path)
        assert _LEGACY_METER.search(maintained_prose) is None, path


def test_progress_template_is_valid_and_cannot_masquerade_as_live_project_data() -> None:
    template_path = ROOT / TEMPLATE
    root = ET.parse(template_path).getroot()
    text = template_path.read_text(encoding="utf-8")

    assert root.tag.endswith("svg")
    assert root.attrib.get("viewBox") == "0 0 1200 180"
    assert "TEMPLATE / NOT PROJECT DATA" in text
    assert "N/A" in text
    assert "progress-fill" not in text
    assert TEMPLATE not in README.read_text(encoding="utf-8")
    assert TEMPLATE not in ROADMAP.read_text(encoding="utf-8")
