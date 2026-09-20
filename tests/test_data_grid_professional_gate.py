from __future__ import annotations

from collections.abc import Mapping

from swirui import DataGrid, DataGridColumn
from swirui.core import AccessibilityRole
from swirui.rendering import Rect, SceneNodeKind


def _even_rows(row: Mapping[str, object]) -> bool:
    value = row.get("id")
    return isinstance(value, int) and value % 2 == 0


def test_professional_datagrid_gate_composes_identity_filter_sort_edit_and_virtualization() -> None:
    rows = tuple(
        {
            "id": index,
            "name": f"Work item {index}",
            "status": "ready" if index % 4 else "running",
            "score": index % 97,
        }
        for index in range(2_000)
    )
    grid = DataGrid(
        (
            DataGridColumn("id", "ID", width=80.0, min_width=64.0),
            DataGridColumn("name", "Name", width=220.0, min_width=120.0),
            DataGridColumn("status", "Status", width=140.0),
            DataGridColumn("score", "Score", width=100.0),
        ),
        rows,
        bounds=Rect(0.0, 0.0, 360.0, 180.0),
        key="professional-grid",
        row_height=28.0,
        header_height=40.0,
        selection_mode="multiple",
        editable_columns=("name", "status"),
        row_filter=_even_rows,
        row_key="id",
        accessible_name="Professional workload table",
    )

    assert grid.source_row_count == 2_000
    assert len(grid.rows) == 1_000
    assert grid.is_filtered is True

    grid.sort_by("score", descending=True)
    grid.select_rows((0, 1, 2), primary_index=1, ensure_visible=False)
    selected_ids = tuple(row["id"] for row in grid.selected_rows)
    primary_id = grid.selected_row["id"] if grid.selected_row is not None else None

    replacement = tuple(
        {
            **row,
            "name": f"{row['name']} refreshed",
        }
        for row in rows
    )
    grid.set_rows(replacement)

    assert tuple(row["id"] for row in grid.selected_rows) == selected_ids
    assert grid.selected_row is not None
    assert grid.selected_row["id"] == primary_id
    assert str(grid.selected_row["name"]).endswith(" refreshed")

    edit_index = grid.selected_index
    assert edit_index is not None
    grid.begin_edit(edit_index, "name", ensure_visible=False)
    grid.set_edit_text("Edited through professional gate")
    grid.commit_edit()

    assert grid.selected_row is not None
    assert grid.selected_row["id"] == primary_id
    assert grid.selected_row["name"] == "Edited through professional gate"
    assert tuple(row["id"] for row in grid.selected_rows) == selected_ids

    grid.resize_column("name", 260.0)
    assert next(column for column in grid.columns if column.key == "name").resolved_width == 260.0
    grid.move_column("status", 1)
    assert tuple(column.key for column in grid.columns) == ("id", "status", "name", "score")

    grid.scroll_to_row(len(grid.rows) - 1)
    assert grid.scroll_offset > 0.0
    assert len(grid.visible_row_range) < len(grid.rows)
    assert len(grid.visible_column_keys) < len(grid.columns)

    scene = grid.build_scene_node()
    visible_row_nodes = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.RECTANGLE
        and node.key.startswith("professional-grid:row:")
    ]
    assert len(visible_row_nodes) == len(grid.visible_row_range)

    accessibility = grid.accessibility_snapshot(focused=grid)
    assert accessibility.role is AccessibilityRole.TABLE
    assert accessibility.row_count == len(grid.rows)
    assert accessibility.column_count == len(grid.columns)
    assert any(child.role is AccessibilityRole.COLUMN_HEADER for child in accessibility.children)
    visible_accessible_rows = [
        child for child in accessibility.children if child.role is AccessibilityRole.ROW
    ]
    assert len(visible_accessible_rows) == len(grid.visible_row_range)
    assert all(
        any(cell.role is AccessibilityRole.CELL for cell in row.children)
        for row in visible_accessible_rows
    )

    grid.clear_filter()
    assert grid.is_filtered is False
    assert len(grid.rows) == 2_000
    assert grid.source_row_count == 2_000
    assert grid.selected_row is not None
    assert grid.selected_row["id"] == primary_id
