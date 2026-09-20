from __future__ import annotations

import pytest

from swirui import DataGrid, DataGridColumn, Window, mount
from swirui.core import AccessibilityRole, Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect, SceneNodeKind


def _rows(count: int) -> list[dict[str, object]]:
    return [
        {"id": index, "name": f"Item {index}", "status": "Ready" if index % 2 else "Idle"}
        for index in range(count)
    ]


def _grid(*, row_count: int = 100) -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=72.0),
            DataGridColumn("name", "Name", width=180.0),
            DataGridColumn("status", "Status", width=120.0),
        ),
        _rows(row_count),
        key="jobs",
        bounds=Rect(20.0, 20.0, 380.0, 130.0),
        row_height=30.0,
        header_height=40.0,
    )


def test_datagrid_validates_columns_and_snapshots_rows() -> None:
    with pytest.raises(ValueError, match="at least one column"):
        DataGrid((), (), bounds=Rect(0.0, 0.0, 200.0, 120.0))

    with pytest.raises(ValueError, match="unique"):
        DataGrid(
            (DataGridColumn("id", "One"), DataGridColumn("id", "Two")),
            (),
            bounds=Rect(0.0, 0.0, 200.0, 120.0),
        )

    source = [{"id": 7, "name": "Original"}]
    grid = DataGrid(
        (DataGridColumn("id", "ID"), DataGridColumn("name", "Name")),
        source,
        bounds=Rect(0.0, 0.0, 320.0, 120.0),
    )
    source[0]["name"] = "Mutated"

    assert grid.rows[0]["name"] == "Original"
    assert grid.accessibility_role is AccessibilityRole.TABLE
    assert grid.focusable is True


def test_datagrid_compiles_only_rows_intersecting_viewport() -> None:
    grid = _grid()

    scene = grid.build_scene_node()
    row_keys = [child.key for child in scene.children if ":row:" in child.key]

    assert scene.kind is SceneNodeKind.RECTANGLE
    assert scene.clip_to_bounds is True
    assert grid.visible_row_range == range(0, 3)
    assert row_keys == ["jobs:row:0", "jobs:row:1", "jobs:row:2"]

    grid.scroll_by(45.0)
    scene = grid.build_scene_node()
    row_keys = [child.key for child in scene.children if ":row:" in child.key]

    assert grid.scroll_offset == pytest.approx(45.0)
    assert grid.visible_row_range == range(1, 5)
    assert row_keys == ["jobs:row:1", "jobs:row:2", "jobs:row:3", "jobs:row:4"]


def test_pointer_selection_uses_scroll_offset_and_emits_row_snapshot() -> None:
    window = Window(width=460, height=220)
    grid = _grid()
    runtime = mount(window, grid)
    selected: list[Event] = []
    grid.on("selection_changed", selected.append)
    handle = NativeWindowHandle(1)

    grid.scroll_by(45.0)
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=60.0,
            y=70.0,
            button=PointerButton.LEFT,
        )
    )

    assert window.focused_component is grid
    assert grid.selected_index == 1
    assert grid.selected_row is not None
    assert grid.selected_row["name"] == "Item 1"
    assert selected[-1].data["index"] == 1
    assert selected[-1].data["row"]["id"] == 1
    runtime.unmount()


def test_keyboard_navigation_keeps_selection_visible() -> None:
    window = Window(width=460, height=220)
    grid = _grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)

    grid.select_row(10)
    assert grid.scroll_offset == pytest.approx(240.0)

    window.focus_component(grid)
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x28)
    )
    assert grid.selected_index == 11
    assert grid.scroll_offset == pytest.approx(270.0)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x23)
    )
    assert grid.selected_index == 99
    assert grid.scroll_offset == pytest.approx(2910.0)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x24)
    )
    assert grid.selected_index == 0
    assert grid.scroll_offset == 0.0
    runtime.unmount()


def test_rows_replacement_clamps_scroll_and_drops_invalid_selection() -> None:
    grid = _grid()
    grid.select_row(99)
    assert grid.selected_index == 99
    assert grid.scroll_offset > 0.0

    grid.set_rows(_rows(2))

    assert grid.selected_index is None
    assert grid.scroll_offset == 0.0
    assert grid.visible_row_range == range(0, 2)


def test_sorting_is_stable_three_state_and_preserves_selected_row() -> None:
    grid = DataGrid(
        (
            DataGridColumn("id", "ID", width=72.0),
            DataGridColumn("group", "Group", width=120.0),
            DataGridColumn("name", "Name", width=180.0),
        ),
        (
            {"id": 3, "group": "b", "name": "Three"},
            {"id": 1, "group": "a", "name": "One"},
            {"id": 2, "group": "a", "name": "Two"},
        ),
        key="sorted",
        bounds=Rect(0.0, 0.0, 300.0, 160.0),
    )
    grid.select_row(2, ensure_visible=False)
    selected = grid.selected_row

    grid.toggle_sort("group")
    assert grid.sort_column_key == "group"
    assert grid.sort_descending is False
    assert [row["id"] for row in grid.rows] == [1, 2, 3]
    assert grid.selected_row is selected
    assert grid.selected_index == 1

    grid.toggle_sort("group")
    assert grid.sort_descending is True
    assert [row["id"] for row in grid.rows] == [3, 1, 2]
    assert grid.selected_row is selected
    assert grid.selected_index == 2

    grid.toggle_sort("group")
    assert grid.sort_column_key is None
    assert [row["id"] for row in grid.rows] == [3, 1, 2]
    assert grid.selected_row is selected


def test_column_resize_reorder_and_horizontal_virtualization() -> None:
    grid = DataGrid(
        (
            DataGridColumn("id", "ID", width=80.0, min_width=60.0, max_width=120.0),
            DataGridColumn("name", "Name", width=220.0),
            DataGridColumn("status", "Status", width=160.0),
            DataGridColumn("owner", "Owner", width=180.0),
        ),
        _rows(20),
        key="wide",
        bounds=Rect(0.0, 0.0, 260.0, 180.0),
    )

    assert grid.visible_column_keys == ("id", "name")
    grid.scroll_horizontal_by(250.0)
    assert grid.horizontal_scroll_offset == pytest.approx(250.0)
    assert grid.visible_column_keys == ("name", "status", "owner")

    grid.resize_column("id", 200.0)
    assert grid.columns[0].resolved_width == pytest.approx(120.0)
    grid.move_column("owner", 0)
    assert [column.key for column in grid.columns] == ["owner", "id", "name", "status"]
    assert grid.content_width == pytest.approx(680.0)

    scene = grid.build_scene_node()
    visible_cell_keys = {
        node.key
        for node in scene.walk()
        if ":cell:" in node.key and node.kind is SceneNodeKind.GROUP
    }
    assert visible_cell_keys
    assert all(":owner" not in key for key in visible_cell_keys)


def test_header_pointer_sort_and_resize_use_retained_input_routing() -> None:
    window = Window(width=460, height=220)
    grid = _grid(row_count=8)
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=130.0,
            y=35.0,
            button=PointerButton.LEFT,
        )
    )
    assert grid.sort_column_key is None
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=130.0,
            y=35.0,
            button=PointerButton.LEFT,
        )
    )
    assert grid.sort_column_key == "name"
    assert grid.sort_descending is False

    separator_x = grid.bounds.x + grid.columns[0].resolved_width
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=separator_x,
            y=35.0,
            button=PointerButton.LEFT,
        )
    )
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_MOVE,
            handle,
            x=separator_x + 28.0,
            y=35.0,
        )
    )
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=separator_x + 28.0,
            y=35.0,
            button=PointerButton.LEFT,
        )
    )

    assert grid.columns[0].resolved_width == pytest.approx(100.0)
    runtime.unmount()
