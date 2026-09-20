from swirui import (
    AccessibilityRole,
    DataGrid,
    DataGridColumn,
    build_accessibility_tree,
)
from swirui.rendering import Rect


def _grid(*, width: float = 360.0, height: float = 112.0) -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=80.0),
            DataGridColumn("name", "Name", width=160.0),
            DataGridColumn("qty", "Quantity", width=120.0),
        ),
        (
            {"id": 1, "name": "Alpha", "qty": 2},
            {"id": 2, "name": "Beta", "qty": 4},
            {"id": 3, "name": "Gamma", "qty": 8},
            {"id": 4, "name": "Delta", "qty": 16},
        ),
        bounds=Rect(0.0, 0.0, width, height),
        key="orders",
        selection_mode="multiple",
        accessible_name="Orders",
    )


def test_data_grid_accessibility_exposes_table_dimensions_headers_rows_and_cells() -> None:
    grid = _grid()
    grid.activate_cell(1, "qty", ensure_visible=False)
    grid.select_rows((1, 2), primary_index=1, ensure_visible=False)

    tree = build_accessibility_tree(grid, focused=grid)

    assert tree is not None
    assert tree.role is AccessibilityRole.TABLE
    assert tree.name == "Orders"
    assert tree.focused is True
    assert tree.row_count == 4
    assert tree.column_count == 3
    assert tree.value_text == "2 rows selected of 4"

    header = tree.find("orders:a11y:header:qty")
    assert header is not None
    assert header.role is AccessibilityRole.COLUMN_HEADER
    assert header.name == "Quantity"
    assert header.column_index == 2

    row = tree.find("orders:a11y:row:1")
    assert row is not None
    assert row.role is AccessibilityRole.ROW
    assert row.selected is True
    assert row.active is True
    assert row.row_index == 1
    assert row.column_count == 3

    cell = tree.find("orders:a11y:cell:1:qty")
    assert cell is not None
    assert cell.role is AccessibilityRole.CELL
    assert cell.name == "Quantity: 4"
    assert cell.selected is True
    assert cell.active is True
    assert cell.row_index == 1
    assert cell.column_index == 2


def test_data_grid_accessibility_keeps_semantics_virtualized_but_reports_logical_count() -> None:
    grid = _grid(height=76.0)

    tree = build_accessibility_tree(grid)

    assert tree is not None
    assert tree.row_count == 4
    assert tree.find("orders:a11y:row:0") is not None
    assert tree.find("orders:a11y:row:1") is None
    assert tree.find("orders:a11y:row:3") is None


def test_data_grid_accessibility_tracks_horizontal_virtualization() -> None:
    grid = _grid(width=100.0)
    grid.scroll_horizontal_by(200.0)

    tree = build_accessibility_tree(grid)

    assert tree is not None
    assert tree.column_count == 3
    assert tree.find("orders:a11y:header:id") is None
    assert tree.find("orders:a11y:header:name") is not None
    assert tree.find("orders:a11y:header:qty") is not None
