from __future__ import annotations

import pytest

from swirui import DataGrid, DataGridColumn, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def _grid(*, width: float = 260.0) -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=80.0),
            DataGridColumn("name", "Name", width=180.0),
            DataGridColumn("status", "Status", width=140.0),
        ),
        tuple(
            {
                "id": index,
                "name": f"Item {index}",
                "status": "Ready" if index % 2 else "Idle",
            }
            for index in range(20)
        ),
        key="jobs",
        bounds=Rect(20.0, 20.0, width, 140.0),
        row_height=30.0,
        header_height=40.0,
    )


def test_activate_cell_tracks_value_and_reveals_both_axes() -> None:
    grid = _grid(width=220.0)

    grid.activate_cell(8, "status")

    assert grid.selected_index == 8
    assert grid.active_column_key == "status"
    assert grid.active_cell == (8, "status", "Idle")
    assert grid.scroll_offset > 0.0
    assert grid.horizontal_scroll_offset == pytest.approx(180.0)


def test_pointer_selection_establishes_cell_cursor_from_visual_column() -> None:
    window = Window(width=420, height=220)
    grid = _grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=150.0,
            y=75.0,
            button=PointerButton.LEFT,
        )
    )

    assert grid.selected_index == 0
    assert grid.active_column_key == "name"
    assert grid.active_cell == (0, "name", "Item 0")
    runtime.unmount()


def test_left_right_navigation_preserves_row_and_scrolls_active_column_visible() -> None:
    window = Window(width=420, height=220)
    grid = _grid(width=220.0)
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)
    changes: list[tuple[int | None, str]] = []
    grid.on(
        "active_column_changed",
        lambda event: changes.append((event.data["row_index"], event.data["column_key"])),
    )

    grid.activate_cell(5, "name")
    window.focus_component(grid)
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x27)
    )

    assert grid.selected_index == 5
    assert grid.active_column_key == "status"
    assert grid.horizontal_scroll_offset == pytest.approx(180.0)
    assert changes[-1] == (5, "status")

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x28)
    )
    assert grid.selected_index == 6
    assert grid.active_column_key == "status"

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x25)
    )
    assert grid.selected_index == 6
    assert grid.active_column_key == "name"
    assert grid.horizontal_scroll_offset == pytest.approx(80.0)
    runtime.unmount()


def test_horizontal_navigation_initializes_first_cell_when_selection_is_empty() -> None:
    window = Window(width=420, height=220)
    grid = _grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)
    window.focus_component(grid)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x25)
    )

    assert grid.selected_index == 0
    assert grid.active_cell == (0, "id", 0)
    runtime.unmount()
