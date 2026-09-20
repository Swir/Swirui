from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import pytest

from swirui import DataGrid, DataGridColumn, Window, mount
from swirui.core import Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect, SceneNodeKind


def _grid(
    *,
    parser: Callable[[str, object], object] | None = None,
    selection_mode: Literal["single", "multiple"] = "multiple",
) -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=72.0),
            DataGridColumn("name", "Name", width=160.0),
            DataGridColumn("qty", "Quantity", width=110.0),
        ),
        (
            {"id": 1, "name": "Alpha", "qty": 2},
            {"id": 2, "name": "Beta", "qty": 4},
            {"id": 3, "name": "Gamma", "qty": 8},
        ),
        bounds=Rect(0.0, 0.0, 260.0, 116.0),
        key="orders",
        selection_mode=selection_mode,
        editable_columns=("name", "qty"),
        cell_edit_parser=parser,
    )


def test_data_grid_editing_is_opt_in_and_validates_columns() -> None:
    with pytest.raises(KeyError, match="missing"):
        DataGrid(
            (DataGridColumn("id", "ID"),),
            ({"id": 1},),
            bounds=Rect(0.0, 0.0, 160.0, 90.0),
            editable_columns=("missing",),
        )

    grid = _grid()
    assert grid.editable_column_keys == ("name", "qty")

    with pytest.raises(ValueError, match="not editable"):
        grid.begin_edit(0, "id")


def test_data_grid_keyboard_text_edit_commit_and_cancel() -> None:
    window = Window(width=360, height=180)
    grid = _grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)
    committed: list[Event] = []
    cancelled: list[Event] = []
    grid.on("cell_edit_committed", committed.append)
    grid.on("cell_edit_cancelled", cancelled.append)

    grid.activate_cell(0, "name", ensure_visible=False)
    window.focus_component(grid)
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x71)
    )
    assert grid.editing_cell == (0, "name", "Alpha")

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.TEXT_INPUT, handle, text=" X")
    )
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x08)
    )
    assert grid.editing_cell == (0, "name", "Alpha ")

    scene = grid.build_scene_node()
    editor_text = next(
        node for node in scene.walk() if node.key == "orders:editor:text"
    )
    assert editor_text.kind is SceneNodeKind.TEXT
    assert editor_text.text == "Alpha │"

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x0D)
    )
    assert grid.is_editing is False
    assert grid.rows[0]["name"] == "Alpha "
    assert committed[-1].data["column_key"] == "name"
    assert committed[-1].data["old_value"] == "Alpha"
    assert committed[-1].data["value"] == "Alpha "

    grid.begin_edit(0, "name", ensure_visible=False)
    grid.set_edit_text("Discarded")
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x1B)
    )
    assert grid.rows[0]["name"] == "Alpha "
    assert cancelled[-1].data["reason"] == "escape"
    runtime.unmount()


def test_data_grid_edit_commit_preserves_multi_selection_and_resorts_row() -> None:
    grid = _grid()
    grid.sort_by("name")
    grid.select_rows((0, 1), primary_index=0, ensure_visible=False)

    grid.begin_edit(0, "name", ensure_visible=False)
    grid.set_edit_text("Zulu")
    grid.commit_edit()

    assert [row["name"] for row in grid.rows] == ["Beta", "Gamma", "Zulu"]
    assert grid.selected_index == 2
    assert grid.selected_row is not None
    assert grid.selected_row["id"] == 1
    assert {row["id"] for row in grid.selected_rows} == {1, 2}
    assert grid.active_column_key == "name"


def test_data_grid_edit_parser_can_preserve_typed_values() -> None:
    def parser(text: str, old_value: object) -> object:
        if isinstance(old_value, int):
            return int(text)
        return text

    grid = _grid(parser=parser)
    grid.activate_cell(1, "qty", ensure_visible=False)
    grid.begin_edit()
    grid.set_edit_text("42")
    grid.commit_edit()

    assert grid.rows[1]["qty"] == 42
    assert isinstance(grid.rows[1]["qty"], int)


def test_data_grid_row_replacement_and_sort_cancel_stale_edits() -> None:
    grid = _grid()
    cancelled: list[Event] = []
    grid.on("cell_edit_cancelled", cancelled.append)

    grid.begin_edit(0, "name", ensure_visible=False)
    grid.set_rows(({"id": 9, "name": "Replacement", "qty": 1},))
    assert grid.is_editing is False
    assert cancelled[-1].data["reason"] == "rows_replaced"

    grid.begin_edit(0, "name", ensure_visible=False)
    grid.sort_by("name", descending=True)
    assert grid.is_editing is False
    assert cancelled[-1].data["reason"] == "sort_changed"


def test_pointer_navigation_cancels_uncommitted_cell_buffer() -> None:
    grid = _grid()
    grid.begin_edit(0, "name", ensure_visible=False)
    grid.set_edit_text("Temporary")

    event = Event(
        "pointer_down",
        grid,
        data={
            "event": PlatformEvent(
                PlatformEventKind.POINTER_DOWN,
                NativeWindowHandle(1),
                x=40.0,
                y=92.0,
                button=PointerButton.LEFT,
            )
        },
    )
    grid._on_pointer_down(event)

    assert grid.is_editing is False
    assert grid.rows[0]["name"] == "Alpha"
