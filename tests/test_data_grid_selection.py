from __future__ import annotations

from swirui import DataGrid, DataGridColumn, Window, mount
from swirui.core import Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def _rows(count: int) -> list[dict[str, object]]:
    return [
        {"id": index, "name": f"Item {index}", "group": "a" if index % 2 else "b"}
        for index in range(count)
    ]


def _grid(*, row_count: int = 8, selection_mode: str = "multiple") -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=72.0),
            DataGridColumn("name", "Name", width=180.0),
            DataGridColumn("group", "Group", width=100.0),
        ),
        _rows(row_count),
        key="multi",
        bounds=Rect(20.0, 20.0, 380.0, 220.0),
        row_height=30.0,
        header_height=40.0,
        selection_mode=selection_mode,
    )


def test_multiple_selection_programmatic_api_and_event_payload() -> None:
    grid = _grid()
    events: list[Event] = []
    grid.on("selection_changed", events.append)

    grid.select_rows((1, 3, 5), primary_index=3)

    assert grid.selection_mode == "multiple"
    assert grid.selected_indices == (1, 3, 5)
    assert [row["id"] for row in grid.selected_rows] == [1, 3, 5]
    assert grid.selected_index == 3
    assert events[-1].data["indices"] == (1, 3, 5)
    assert [row["id"] for row in events[-1].data["rows"]] == [1, 3, 5]
    assert grid.accessible_value_text == "3 rows selected of 8"

    grid.clear_selection()
    assert grid.selected_indices == ()
    assert grid.selected_index is None
    assert grid.accessible_value_text == "0 rows selected of 8"


def test_single_selection_mode_remains_backward_compatible() -> None:
    grid = _grid(selection_mode="single")

    grid.select_row(2)
    assert grid.selected_indices == (2,)
    assert grid.selected_row is not None
    assert grid.selected_row["id"] == 2

    grid.select_row(4)
    assert grid.selected_indices == (4,)

    try:
        grid.select_rows((1, 2))
    except ValueError as exc:
        assert "single selection" in str(exc)
    else:
        raise AssertionError("single selection must reject multiple explicit indices")


def test_pointer_ctrl_toggle_and_shift_range_use_retained_routing() -> None:
    window = Window(width=460, height=300)
    grid = _grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)

    def click(row: int, *, ctrl: bool = False, shift: bool = False) -> None:
        y = grid.bounds.y + 40.0 + (row * 30.0) + 15.0
        window._apply_platform_event(
            PlatformEvent(
                PlatformEventKind.POINTER_DOWN,
                handle,
                x=80.0,
                y=y,
                button=PointerButton.LEFT,
                ctrl=ctrl,
                shift=shift,
            )
        )

    click(1)
    click(3, ctrl=True)
    assert grid.selected_indices == (1, 3)
    assert grid.selected_index == 3

    click(5, shift=True)
    assert grid.selected_indices == (3, 4, 5)
    assert grid.selected_index == 5
    runtime.unmount()


def test_keyboard_shift_range_ctrl_a_and_ctrl_space() -> None:
    window = Window(width=460, height=300)
    grid = _grid(row_count=10)
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)
    grid.select_row(2)
    window.focus_component(grid)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x28, shift=True)
    )
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x28, shift=True)
    )
    assert grid.selected_indices == (2, 3, 4)
    assert grid.selected_index == 4

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x41, ctrl=True)
    )
    assert grid.selected_indices == tuple(range(10))
    assert grid.selected_index == 4

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x20, ctrl=True)
    )
    assert 4 not in grid.selected_indices
    assert grid.selected_index == 3
    runtime.unmount()


def test_sorting_and_row_replacement_preserve_complete_multi_selection() -> None:
    grid = DataGrid(
        (
            DataGridColumn("id", "ID"),
            DataGridColumn("group", "Group"),
        ),
        (
            {"id": 3, "group": "b"},
            {"id": 1, "group": "a"},
            {"id": 2, "group": "a"},
        ),
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        selection_mode="multiple",
    )
    grid.select_rows((0, 2), primary_index=2)

    grid.sort_by("group")
    assert [row["id"] for row in grid.rows] == [1, 2, 3]
    assert grid.selected_indices == (1, 2)
    assert grid.selected_row is not None
    assert grid.selected_row["id"] == 2

    grid.set_rows(({"id": 2, "group": "a"}, {"id": 3, "group": "b"}))
    assert grid.selected_indices == (0, 1)
    assert grid.selected_index == 0
    assert [row["id"] for row in grid.selected_rows] == [2, 3]


def test_invalid_selection_mode_and_select_all_guard() -> None:
    try:
        _grid(selection_mode="bogus")
    except ValueError as exc:
        assert "selection_mode" in str(exc)
    else:
        raise AssertionError("invalid selection mode must fail")

    grid = _grid(selection_mode="single")
    try:
        grid.select_all()
    except ValueError as exc:
        assert "multiple" in str(exc)
    else:
        raise AssertionError("select_all must require multiple mode")
