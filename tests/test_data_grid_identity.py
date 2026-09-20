from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from swirui import DataGrid, DataGridColumn
from swirui.rendering import Rect


def _grid(
    rows: Sequence[Mapping[str, object]],
    *,
    editable_columns: Sequence[str] = (),
) -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=72.0),
            DataGridColumn("name", "Name", width=160.0),
            DataGridColumn("status", "Status", width=120.0),
        ),
        rows,
        bounds=Rect(0.0, 0.0, 260.0, 116.0),
        selection_mode="multiple",
        editable_columns=editable_columns,
        row_key="id",
    )


def test_row_key_preserves_multi_selection_across_immutable_row_replacement() -> None:
    grid = _grid(
        (
            {"id": 1, "name": "Alpha", "status": "queued"},
            {"id": 2, "name": "Beta", "status": "queued"},
            {"id": 3, "name": "Gamma", "status": "queued"},
        )
    )
    grid.select_rows((0, 1), primary_index=1, ensure_visible=False)

    grid.set_rows(
        (
            {"id": 2, "name": "Beta v2", "status": "running"},
            {"id": 1, "name": "Alpha v2", "status": "done"},
            {"id": 3, "name": "Gamma v2", "status": "queued"},
        )
    )

    assert grid.row_key == "id"
    assert [row["id"] for row in grid.selected_rows] == [2, 1]
    assert grid.selected_index == 0
    assert grid.selected_row is not None
    assert grid.selected_row["name"] == "Beta v2"
    assert grid.accessible_value_text == "2 rows selected of 3"


def test_row_key_composes_with_filtering_and_prunes_only_hidden_identity() -> None:
    grid = DataGrid(
        (
            DataGridColumn("id", "ID", width=72.0),
            DataGridColumn("name", "Name", width=160.0),
            DataGridColumn("visible", "Visible", width=90.0),
        ),
        (
            {"id": 1, "name": "Alpha", "visible": True},
            {"id": 2, "name": "Beta", "visible": True},
            {"id": 3, "name": "Gamma", "visible": True},
        ),
        bounds=Rect(0.0, 0.0, 260.0, 116.0),
        selection_mode="multiple",
        row_key="id",
        row_filter=lambda row: row.get("visible") is True,
    )
    grid.select_rows((0, 1), primary_index=1, ensure_visible=False)

    grid.set_rows(
        (
            {"id": 2, "name": "Beta updated", "visible": True},
            {"id": 1, "name": "Alpha updated", "visible": False},
            {"id": 3, "name": "Gamma updated", "visible": True},
        )
    )

    assert [row["id"] for row in grid.rows] == [2, 3]
    assert [row["id"] for row in grid.selected_rows] == [2]
    assert grid.selected_index == 0
    assert grid.source_row_count == 3


def test_row_key_keeps_edit_source_lookup_stable() -> None:
    grid = _grid(
        (
            {"id": 1, "name": "Alpha", "status": "queued"},
            {"id": 2, "name": "Beta", "status": "queued"},
        ),
        editable_columns=("name",),
    )
    grid.select_row(1, ensure_visible=False)
    grid.begin_edit(1, "name", ensure_visible=False)
    grid.set_edit_text("Beta edited")

    grid.commit_edit()

    assert grid.selected_row is not None
    assert grid.selected_row["id"] == 2
    assert grid.selected_row["name"] == "Beta edited"
    assert grid.source_row_count == 2


def test_row_key_requires_present_hashable_unique_identity_values() -> None:
    with pytest.raises(KeyError, match="missing configured row_key"):
        _grid(({"id": 1, "name": "Alpha", "status": "queued"}, {"name": "Beta"}))

    with pytest.raises(TypeError, match="must be hashable"):
        _grid(({"id": [1], "name": "Alpha", "status": "queued"},))

    with pytest.raises(ValueError, match="must contain unique values"):
        _grid(
            (
                {"id": 1, "name": "Alpha", "status": "queued"},
                {"id": 1, "name": "Beta", "status": "running"},
            )
        )


def test_row_key_column_cannot_be_editable() -> None:
    with pytest.raises(ValueError, match="row_key cannot also be an editable column"):
        _grid(
            ({"id": 1, "name": "Alpha", "status": "queued"},),
            editable_columns=("id",),
        )
