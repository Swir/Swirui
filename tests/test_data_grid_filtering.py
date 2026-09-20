from __future__ import annotations

from collections.abc import Mapping

from swirui import DataGrid, DataGridColumn
from swirui.core import Event
from swirui.rendering import Rect


def _grid(*, row_filter=None) -> DataGrid:  # type: ignore[no-untyped-def]
    def parser(text: str, old_value: object) -> object:
        return int(text) if isinstance(old_value, int) else text

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
            {"id": 4, "name": "Delta", "qty": 16},
        ),
        bounds=Rect(0.0, 0.0, 260.0, 116.0),
        key="orders",
        selection_mode="multiple",
        editable_columns=("name", "qty"),
        cell_edit_parser=parser,
        row_filter=row_filter,
    )


def _qty_at_least(minimum: int):  # type: ignore[no-untyped-def]
    def predicate(row: Mapping[str, object]) -> bool:
        value = row.get("qty")
        return isinstance(value, int) and value >= minimum

    return predicate


def test_initial_filter_composes_with_sort_and_preserves_source_rows() -> None:
    grid = _grid(row_filter=_qty_at_least(4))

    assert grid.is_filtered is True
    assert grid.source_row_count == 4
    assert [row["name"] for row in grid.rows] == ["Beta", "Gamma", "Delta"]

    grid.sort_by("name", descending=True)
    assert [row["name"] for row in grid.rows] == ["Gamma", "Delta", "Beta"]

    grid.clear_filter()
    assert grid.is_filtered is False
    assert grid.source_row_count == 4
    assert [row["name"] for row in grid.rows] == ["Gamma", "Delta", "Beta", "Alpha"]


def test_filter_change_preserves_only_selection_that_remains_visible() -> None:
    grid = _grid()
    events: list[Event] = []
    grid.on("filter_changed", events.append)
    grid.select_rows((1, 2), primary_index=2, ensure_visible=False)

    predicate = _qty_at_least(8)
    grid.set_filter(predicate)

    assert grid.row_filter is predicate
    assert [row["id"] for row in grid.selected_rows] == [3]
    assert grid.selected_index == 0
    assert grid.selected_row is not None
    assert grid.selected_row["id"] == 3
    assert events[-1].data == {
        "active": True,
        "visible_count": 2,
        "source_count": 4,
    }


def test_row_replacement_reapplies_active_filter() -> None:
    grid = _grid(row_filter=_qty_at_least(10))
    grid.set_rows(
        (
            {"id": 10, "name": "Low", "qty": 1},
            {"id": 11, "name": "High", "qty": 10},
            {"id": 12, "name": "Higher", "qty": 20},
        )
    )

    assert grid.source_row_count == 3
    assert [row["id"] for row in grid.rows] == [11, 12]
    assert grid.accessible_value_text == "0 rows selected of 2"


def test_edit_commit_can_remove_row_from_filtered_view_and_repairs_selection() -> None:
    grid = _grid(row_filter=_qty_at_least(4))
    grid.activate_cell(0, "qty", ensure_visible=False)
    grid.begin_edit()
    grid.set_edit_text("1")
    grid.commit_edit()

    assert [row["id"] for row in grid.rows] == [3, 4]
    assert grid.selected_indices == ()
    assert grid.selected_index is None
    assert grid.is_editing is False
    assert grid.source_row_count == 4


def test_changing_filter_cancels_stale_edit_buffer() -> None:
    grid = _grid()
    cancelled: list[Event] = []
    grid.on("cell_edit_cancelled", cancelled.append)
    grid.begin_edit(1, "name", ensure_visible=False)
    grid.set_edit_text("Temporary")

    grid.set_filter(_qty_at_least(8))

    assert grid.is_editing is False
    assert cancelled[-1].data["reason"] == "filter_changed"
    assert [row["id"] for row in grid.rows] == [3, 4]
