"""Interactive retained DataGrid demo with thousands of virtualized rows."""

from collections.abc import Mapping

from swirui import App, Component, DataGrid, DataGridColumn, Label, Window, mount
from swirui.core import Event
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI DataGrid")
    window = app.add_window(Window(title="SwirUI — DataGrid", width=920, height=620))
    root = Component("DataGrid demo")

    title = Label(
        "SwirUI DataGrid — virtualized professional table",
        bounds=Rect(32.0, 24.0, 760.0, 38.0),
        font_size=25.0,
        color=Color.from_hex("#62E5FF"),
    )
    status = Label(
        "Click headers to sort, drag header separators to resize, use ↑ ↓ Home End PageUp PageDown.",
        bounds=Rect(32.0, 68.0, 840.0, 28.0),
        font_size=15.0,
        color=Color.from_hex("#DDF5FF"),
    )
    columns = (
        DataGridColumn("id", "ID", width=82.0, min_width=64.0, max_width=140.0),
        DataGridColumn("task", "Task", width=360.0, min_width=180.0),
        DataGridColumn("owner", "Owner", width=180.0),
        DataGridColumn("status", "Status", width=180.0),
    )
    rows = [
        {
            "id": index + 1,
            "task": f"Retained workload item {index + 1}",
            "owner": "SwirUI Runtime" if index % 3 else "Native Core",
            "status": "Ready" if index % 5 else "GPU verified",
        }
        for index in range(2500)
    ]
    grid = DataGrid(
        columns,
        rows,
        key="workloads",
        bounds=Rect(32.0, 112.0, 850.0, 470.0),
        row_height=34.0,
        accessible_name="SwirUI workload table",
        accessible_description="Virtualized retained table with 2500 rows.",
    )

    def selection_changed(event: Event) -> None:
        row = event.data.get("row")
        if isinstance(row, Mapping):
            status.text = f"Selected #{row['id']}: {row['task']} — {row['status']}"

    def sort_changed(event: Event) -> None:
        column_key = event.data.get("column_key")
        if column_key is None:
            status.text = "Source row order restored."
            return
        direction = "descending" if event.data.get("descending") else "ascending"
        status.text = f"Sorted by {column_key} ({direction})."

    grid.on("selection_changed", selection_changed)
    grid.on("sort_changed", sort_changed)
    root.add(title, status, grid)
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
