from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "swirui_progress_ascii", ROOT / "tools" / "progress_svg.py"
)
assert SPEC is not None and SPEC.loader is not None
progress = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = progress
SPEC.loader.exec_module(progress)

ProgressData = progress.ProgressData
check_outputs = progress.check_outputs
parse_progress = progress.parse_progress
render_ascii = progress.render_ascii


def _roadmap(percent: str, completed: int, total: int = 12) -> str:
    boxes = ["- [x] done"] * completed + ["- [ ] pending"] * (total - completed)
    return (
        "# Roadmap\n\n"
        f"**Overall completion: {percent}%**\n\n"
        "## 0.4 Alpha — Core Widgets\n\n"
        "- [x] completed previous milestone\n\n"
        "## 0.5 Alpha — Layout Engine\n\n"
        + "\n".join(boxes)
        + "\n\n## 0.6 Alpha — Reactive Runtime\n"
    )


def test_parse_progress_reproduces_verified_weighting() -> None:
    data = parse_progress(_roadmap("59", completed=3))
    assert data.percentage == Decimal("59")
    assert data.completed == 3
    assert data.total == 12
    assert data.status == "IN PROGRESS"


def test_parse_progress_rejects_stale_documented_percentage() -> None:
    with pytest.raises(ValueError, match="stale or contradictory"):
        parse_progress(_roadmap("58", completed=3))


def test_completed_milestone_scope_does_not_imply_project_100_percent() -> None:
    data = parse_progress(_roadmap("68", completed=12))
    assert data.status == "COMPLETE"
    assert data.percentage == Decimal("68")
    assert "[##############------] 68.0%" in render_ascii(data)


def test_ascii_progress_is_bounded_and_deterministic() -> None:
    data = ProgressData(
        project="SwirUI",
        scope="0.5 Alpha — Layout Engine",
        status="IN PROGRESS",
        percentage=Decimal("59"),
        completed=3,
        total=12,
        counter_label="layout groups verified",
    )
    block = render_ascii(data)
    assert "[############--------] 59.0%" in block
    assert "3 / 12 layout groups verified" in block
    assert "█" not in block


def test_committed_ascii_progress_is_current() -> None:
    assert check_outputs(ROOT) == []
