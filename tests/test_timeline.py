from __future__ import annotations

import pytest

from swirui import Timeline, TimelineItem, TimelineOrientation
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def _items() -> tuple[TimelineItem, ...]:
    return (
        TimelineItem("plan", "Plan", "09:00", "Define the retained widget contract."),
        TimelineItem("build", "Build", "10:30", "Compile the GPU-backed scene.", disabled=True),
        TimelineItem("verify", "Verify", "12:00", "Run native qualification."),
    )


def test_timeline_preserves_selection_by_stable_key_and_skips_disabled() -> None:
    timeline = Timeline(
        _items(),
        bounds=Rect(0.0, 0.0, 520.0, 240.0),
        key="timeline",
        selected_key="verify",
    )

    timeline.set_items(
        (
            TimelineItem("verify", "Verify", "12:15", "Run exact-head qualification."),
            TimelineItem("plan", "Plan", "09:15"),
            TimelineItem("ship", "Ship", "14:00"),
        )
    )

    assert timeline.selected_index == 0
    assert timeline.selected_item is not None
    assert timeline.selected_item.key == "verify"
    assert timeline.selected_item.timestamp == "12:15"
    assert timeline.accessible_value_text == "Verify, 12:15, item 1 of 3"

    timeline.select_key("ship")
    assert timeline.selected_item is not None
    assert timeline.selected_item.key == "ship"


def test_timeline_activation_scene_and_accessibility_contract() -> None:
    timeline = Timeline(
        _items(),
        bounds=Rect(8.0, 10.0, 560.0, 234.0),
        key="history",
    )
    activated: list[object] = []
    timeline.on("item_activated", lambda event: activated.append(event.data["key"]))

    timeline.activate_selected()
    assert activated == ["plan"]

    scene = timeline.build_scene_node()
    keys = {node.key for node in scene.walk()}
    texts = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert "history:axis" in keys
    assert "history:item:0:marker" in keys
    assert "history:item:2:title" in keys
    assert "Plan" in texts
    assert "12:00" in texts

    snapshot = timeline.accessibility_snapshot(focused=timeline)
    assert snapshot.role is AccessibilityRole.LIST
    assert snapshot.focused is True
    assert snapshot.row_count == 3
    assert snapshot.children[0].role is AccessibilityRole.LIST_ITEM
    assert snapshot.children[0].selected is True
    assert snapshot.children[0].value_text == "09:00"
    assert snapshot.children[1].enabled is False
    assert snapshot.children[2].description == "12:00. Run native qualification."


def test_horizontal_timeline_uses_orientation_specific_geometry() -> None:
    timeline = Timeline(
        _items(),
        bounds=Rect(20.0, 30.0, 360.0, 120.0),
        key="horizontal-history",
        orientation=TimelineOrientation.HORIZONTAL,
        item_extent=120.0,
    )

    second = timeline.item_bounds(1)
    assert second == Rect(140.0, 30.0, 120.0, 120.0)

    scene = timeline.build_scene_node()
    axis = next(node for node in scene.walk() if node.key == "horizontal-history:axis")
    assert axis.bounds.width > axis.bounds.height
    assert any(node.key == "horizontal-history:item:1:marker" for node in scene.walk())


def test_timeline_validates_identity_and_selection_contract() -> None:
    with pytest.raises(ValueError, match="Duplicate timeline key"):
        Timeline(
            (
                TimelineItem("same", "A", "09:00"),
                TimelineItem("same", "B", "10:00"),
            ),
            bounds=Rect(0.0, 0.0, 320.0, 160.0),
        )

    with pytest.raises(ValueError, match="title must not be empty"):
        TimelineItem("bad", " ", "09:00")

    with pytest.raises(ValueError, match="disabled timeline item"):
        Timeline(
            _items(),
            bounds=Rect(0.0, 0.0, 320.0, 160.0),
            selected_key="build",
        )

    timeline = Timeline(
        _items(),
        bounds=Rect(0.0, 0.0, 320.0, 160.0),
    )
    with pytest.raises(KeyError, match="Unknown timeline key"):
        timeline.select_key("missing")
