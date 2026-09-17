from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "swirui_progress_svg", ROOT / "tools" / "progress_svg.py"
)
assert SPEC is not None and SPEC.loader is not None
progress_svg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = progress_svg
SPEC.loader.exec_module(progress_svg)

CARD_TRACK_WIDTH = progress_svg.CARD_TRACK_WIDTH
MINI_TRACK_WIDTH = progress_svg.MINI_TRACK_WIDTH
ProgressData = progress_svg.ProgressData
check_outputs = progress_svg.check_outputs
parse_progress = progress_svg.parse_progress
render_card = progress_svg.render_card
render_mini = progress_svg.render_mini

SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def _roadmap(percent: str, completed: int, total: int = 15) -> str:
    boxes = ["- [x] done"] * completed + ["- [ ] pending"] * (total - completed)
    return (
        "# Roadmap\n\n"
        f"**Overall completion: {percent}%**\n\n"
        "## 0.4 Alpha — Core Widgets\n\n"
        + "\n".join(boxes)
        + "\n\n## 0.5 Alpha — Layout Engine\n"
    )


def _fill_width(svg: str) -> Decimal | None:
    root = ET.fromstring(svg)
    fill = root.find('.//svg:rect[@data-role="progress-fill"]', SVG_NS)
    if fill is None:
        return None
    return Decimal(fill.attrib["width"])


def test_parse_progress_reproduces_verified_weighting() -> None:
    data = parse_progress(_roadmap("51", completed=10))

    assert data.percentage == Decimal("51")
    assert data.completed == 10
    assert data.total == 15
    assert data.status == "IN PROGRESS"


def test_parse_progress_rejects_stale_documented_percentage() -> None:
    with pytest.raises(ValueError, match="stale or contradictory"):
        parse_progress(_roadmap("50", completed=10))


def test_completed_milestone_scope_does_not_imply_project_100_percent() -> None:
    data = parse_progress(_roadmap("56", completed=15))

    assert data.status == "COMPLETE"
    assert data.percentage == Decimal("56")
    assert data.counter_text == "15 / 15 widget groups verified"


def test_empty_scope_is_unverifiable_instead_of_zero_percent() -> None:
    with pytest.raises(ValueError, match="No checklist items"):
        parse_progress(_roadmap("41", completed=0, total=0))


@pytest.mark.parametrize(
    ("percentage", "card_width", "mini_width"),
    [
        (Decimal("0"), None, None),
        (Decimal("51"), Decimal("561"), Decimal("357")),
        (Decimal("100"), CARD_TRACK_WIDTH, MINI_TRACK_WIDTH),
    ],
)
def test_progress_fill_is_bounded(
    percentage: Decimal,
    card_width: Decimal | None,
    mini_width: Decimal | None,
) -> None:
    data = ProgressData(
        project="SwirUI",
        scope="0.4 Alpha — Core Widgets",
        status="IN PROGRESS",
        percentage=percentage,
        completed=10,
        total=15,
        counter_label="widget groups verified",
    )

    assert _fill_width(render_card(data)) == card_width
    assert _fill_width(render_mini(data)) == mini_width


def test_unknown_progress_is_na_and_has_no_fill() -> None:
    data = ProgressData(
        project="SwirUI",
        scope="Unknown scope",
        status="PLANNING",
        percentage=None,
        completed=None,
        total=None,
        counter_label="items verified",
    )

    card = render_card(data)
    assert "N/A" in card
    assert _fill_width(card) is None


def test_long_scope_expands_card_instead_of_overlapping() -> None:
    data = ProgressData(
        project="SwirUI",
        scope=(
            "A deliberately long verified milestone label that must wrap onto another line "
            "without colliding with the progress track"
        ),
        status="IN PROGRESS",
        percentage=Decimal("51"),
        completed=10,
        total=15,
        counter_label="items verified",
    )

    root = ET.fromstring(render_card(data))
    assert int(root.attrib["height"]) > 180


def test_committed_progress_assets_are_current() -> None:
    assert check_outputs(ROOT) == []
