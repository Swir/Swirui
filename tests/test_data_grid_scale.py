from __future__ import annotations

from swirui import DataGrid, DataGridColumn
from swirui.rendering import Rect


def test_datagrid_large_dataset_scene_cost_stays_viewport_bounded() -> None:
    columns = tuple(
        DataGridColumn(f"c{index}", f"Column {index}", width=120.0)
        for index in range(24)
    )
    rows = [
        {f"c{column}": (row * 100) + column for column in range(24)}
        for row in range(10_000)
    ]
    grid = DataGrid(
        columns,
        rows,
        key="large-grid",
        bounds=Rect(0.0, 0.0, 460.0, 240.0),
        row_height=28.0,
        header_height=40.0,
    )

    grid.sort_by("c0", descending=True)
    grid.scroll_to_row(9_999)
    grid.scroll_horizontal_by(1_800.0)
    scene = grid.build_scene_node()
    nodes = tuple(scene.walk())

    assert len(grid.visible_row_range) <= 8
    assert len(grid.visible_column_keys) <= 5
    assert len(nodes) < 120
    assert grid.rows[0]["c0"] == 999_900
    assert grid.rows[-1]["c0"] == 0
