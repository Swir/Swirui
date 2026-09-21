from __future__ import annotations

import pytest

from swirui import Inspector, PropertyEditorKind, PropertyGrid, PropertyItem
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def _items() -> tuple[PropertyItem, ...]:
    return (
        PropertyItem("title", "Title", "Canvas", category="General"),
        PropertyItem("visible", "Visible", True, category="General"),
        PropertyItem(
            "opacity",
            "Opacity",
            0.75,
            category="Appearance",
            editor=PropertyEditorKind.FLOAT,
        ),
        PropertyItem("id", "Object ID", "node-7", category="Metadata", read_only=True),
    )


def test_property_grid_preserves_selection_by_stable_key() -> None:
    grid = PropertyGrid(_items(), bounds=Rect(0.0, 0.0, 520.0, 220.0), key="props")

    grid.select_key("opacity")
    grid.set_items(
        (
            PropertyItem("visible", "Visible", False),
            PropertyItem("opacity", "Opacity", 0.9, category="Appearance"),
            PropertyItem("title", "Title", "Scene"),
        )
    )

    assert grid.selected_index == 1
    assert grid.selected_item is not None
    assert grid.selected_item.key == "opacity"
    assert grid.selected_item.value == 0.9
    assert grid.accessible_value_text == "Opacity, property 2 of 3"


def test_property_grid_edits_typed_values_and_reports_changes() -> None:
    grid = PropertyGrid(_items(), bounds=Rect(0.0, 0.0, 520.0, 220.0))
    changes: list[tuple[object, object]] = []
    grid.on(
        "property_changed",
        lambda event: changes.append((event.data["key"], event.data["value"])),
    )

    grid.begin_edit("title").set_edit_buffer("SwirUI").commit_edit()
    assert next(item for item in grid.items if item.key == "title").value == "SwirUI"

    grid.begin_edit("opacity").set_edit_buffer("0.625").commit_edit()
    assert next(item for item in grid.items if item.key == "opacity").value == 0.625
    assert changes == [("title", "SwirUI"), ("opacity", 0.625)]

    grid.begin_edit("opacity").set_edit_buffer("not-a-number")
    with pytest.raises(ValueError, match="valid number"):
        grid.commit_edit()
    assert grid.editing_item is not None
    grid.cancel_edit()
    assert grid.editing_item is None


def test_property_grid_boolean_read_only_scene_and_accessibility() -> None:
    grid = Inspector(
        _items(),
        bounds=Rect(8.0, 10.0, 540.0, 220.0),
        key="inspector",
    )

    grid.select_key("visible").toggle_selected()
    assert next(item for item in grid.items if item.key == "visible").value is False

    grid.begin_edit("id")
    assert grid.editing_item is None
    assert grid.selected_item is not None
    assert grid.selected_item.key == "id"
    with pytest.raises(PermissionError, match="read-only"):
        grid.set_value("id", "replacement")

    scene = grid.build_scene_node()
    texts = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert "General / Visible" in texts
    assert "False" in texts
    assert "Metadata / Object ID" in texts
    assert any(node.key == "inspector:row:3:accent" for node in scene.walk())

    snapshot = grid.accessibility_snapshot(focused=grid)
    assert snapshot.role is AccessibilityRole.TABLE
    assert snapshot.focused is True
    assert snapshot.row_count == 4
    assert snapshot.column_count == 2
    assert snapshot.children[1].role is AccessibilityRole.ROW
    assert snapshot.children[1].selected is False
    assert snapshot.children[1].children[1].role is AccessibilityRole.CELL
    assert snapshot.children[1].children[1].value_text == "False"
    assert snapshot.children[3].selected is True
    assert snapshot.children[3].children[1].enabled is False
    assert snapshot.name == "Inspector"


def test_property_grid_validates_identity_and_editor_contract() -> None:
    with pytest.raises(ValueError, match="Duplicate property key"):
        PropertyGrid(
            (PropertyItem("same", "A", "x"), PropertyItem("same", "B", "y")),
            bounds=Rect(0.0, 0.0, 320.0, 100.0),
        )

    with pytest.raises(TypeError, match="Integer property values"):
        PropertyItem(
            "bad",
            "Bad",
            "one",
            editor=PropertyEditorKind.INTEGER,
        )

    grid = PropertyGrid(
        (PropertyItem("only", "Only", "value"),),
        bounds=Rect(0.0, 0.0, 320.0, 60.0),
    )
    with pytest.raises(KeyError, match="Unknown property key"):
        grid.select_key("missing")
