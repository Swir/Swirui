from __future__ import annotations

import pytest

from swirui import DataGrid, DataGridColumn, Window, mount
from swirui.core import Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def _wide_grid() -> DataGrid:
    rows = tuple({"id": index, "name": f"Item {index}", "status": "Ready"} for index in range(40))
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=80.0),
            DataGridColumn("name", "Name", width=140.0),
            DataGridColumn("status", "Status", width=140.0),
            DataGridColumn("owner", "Owner", width=140.0),
        ),
        rows,
        key="drag-grid",
        bounds=Rect(20.0, 20.0, 260.0, 180.0),
        row_height=30.0,
        header_height=40.0,
    )


def _pointer(
    window: Window,
    kind: PlatformEventKind,
    *,
    x: float,
    y: float = 35.0,
    button: PointerButton | None = None,
) -> None:
    window._apply_platform_event(
        PlatformEvent(
            kind,
            NativeWindowHandle(1),
            x=x,
            y=y,
            button=button,
        )
    )


def test_direct_header_drag_reorders_without_transient_sort() -> None:
    window = Window(width=420, height=240)
    grid = _wide_grid()
    runtime = mount(window, grid)
    started: list[Event] = []
    finished: list[Event] = []
    sorted_events: list[Event] = []
    grid.on("column_drag_started", started.append)
    grid.on("column_drag_finished", finished.append)
    grid.on("sort_changed", sorted_events.append)

    _pointer(
        window,
        PlatformEventKind.POINTER_DOWN,
        x=50.0,
        button=PointerButton.LEFT,
    )
    assert grid.sort_column_key is None

    _pointer(window, PlatformEventKind.POINTER_MOVE, x=245.0)
    assert grid.dragging_column_key == "id"
    assert grid.sort_column_key is None
    assert sorted_events == []
    assert [column.key for column in grid.columns] == ["name", "status", "id", "owner"]

    _pointer(
        window,
        PlatformEventKind.POINTER_UP,
        x=245.0,
        button=PointerButton.LEFT,
    )
    assert grid.dragging_column_key is None
    assert grid.sort_column_key is None
    assert sorted_events == []
    assert started[-1].data == {"column_key": "id", "old_index": 0}
    assert finished[-1].data == {"column_key": "id", "old_index": 0, "new_index": 2}
    runtime.unmount()


def test_header_drag_threshold_keeps_click_sort_and_edge_autoscrolls_wide_grid() -> None:
    window = Window(width=420, height=240)
    grid = _wide_grid()
    runtime = mount(window, grid)

    _pointer(
        window,
        PlatformEventKind.POINTER_DOWN,
        x=110.0,
        button=PointerButton.LEFT,
    )
    assert grid.sort_column_key is None
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=114.0)
    assert grid.sort_column_key is None
    _pointer(
        window,
        PlatformEventKind.POINTER_UP,
        x=114.0,
        button=PointerButton.LEFT,
    )
    assert grid.sort_column_key == "name"
    assert [column.key for column in grid.columns] == ["id", "name", "status", "owner"]

    grid.sort_by(None)
    _pointer(
        window,
        PlatformEventKind.POINTER_DOWN,
        x=50.0,
        button=PointerButton.LEFT,
    )
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=278.0)
    assert grid.horizontal_scroll_offset == pytest.approx(36.0)
    assert grid.dragging_column_key == "id"
    _pointer(
        window,
        PlatformEventKind.POINTER_UP,
        x=278.0,
        button=PointerButton.LEFT,
    )
    runtime.unmount()


def test_header_drag_keeps_capture_after_pointer_leaves_grid_bounds() -> None:
    window = Window(width=420, height=240)
    grid = _wide_grid()
    runtime = mount(window, grid)
    finished: list[Event] = []
    grid.on("column_drag_finished", finished.append)

    _pointer(
        window,
        PlatformEventKind.POINTER_DOWN,
        x=50.0,
        button=PointerButton.LEFT,
    )
    assert window.pointer_capture_component is grid

    _pointer(window, PlatformEventKind.POINTER_MOVE, x=390.0)
    assert grid.dragging_column_key == "id"
    assert [column.key for column in grid.columns] == ["name", "status", "owner", "id"]
    assert window.pointer_capture_component is grid

    _pointer(
        window,
        PlatformEventKind.POINTER_UP,
        x=390.0,
        button=PointerButton.LEFT,
    )
    assert grid.dragging_column_key is None
    assert window.pointer_capture_component is None
    assert finished[-1].data == {"column_key": "id", "old_index": 0, "new_index": 3}
    runtime.unmount()


def test_focus_loss_finalizes_active_header_drag_without_stale_gesture() -> None:
    window = Window(width=420, height=240)
    grid = _wide_grid()
    runtime = mount(window, grid)
    finished: list[Event] = []
    grid.on("column_drag_finished", finished.append)

    _pointer(
        window,
        PlatformEventKind.POINTER_DOWN,
        x=50.0,
        button=PointerButton.LEFT,
    )
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=390.0)
    assert grid.dragging_column_key == "id"

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.FOCUS,
            NativeWindowHandle(1),
            focused=False,
        )
    )

    assert window.pointer_capture_component is None
    assert grid.dragging_column_key is None
    assert finished[-1].data == {
        "column_key": "id",
        "old_index": 0,
        "new_index": 3,
        "interrupted": True,
    }
    order = [column.key for column in grid.columns]
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=40.0)
    assert [column.key for column in grid.columns] == order
    runtime.unmount()


def test_focus_loss_finalizes_active_column_resize() -> None:
    window = Window(width=420, height=240)
    grid = _wide_grid()
    runtime = mount(window, grid)
    finished: list[Event] = []
    grid.on("column_resize_finished", finished.append)

    _pointer(
        window,
        PlatformEventKind.POINTER_DOWN,
        x=100.0,
        button=PointerButton.LEFT,
    )
    assert window.pointer_capture_component is grid
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=132.0)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.FOCUS,
            NativeWindowHandle(1),
            focused=False,
        )
    )

    assert window.pointer_capture_component is None
    assert finished[-1].data["column_key"] == "id"
    assert finished[-1].data["width"] == pytest.approx(112.0)
    assert finished[-1].data["interrupted"] is True
    runtime.unmount()
