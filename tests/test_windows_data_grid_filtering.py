import ctypes
import sys
import time
from collections.abc import Callable, Mapping
from typing import Any

import pytest

from swirui import App, DataGrid, DataGridColumn, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.DataGridFiltering.{id(backend):x}"
    return backend


def _user32() -> Any:
    win_dll: Any = ctypes.__dict__["WinDLL"]
    user32: Any = win_dll("user32", use_last_error=True)
    user32.SendMessageW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_ssize_t,
    ]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    return user32


def _lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def _send_click(user32: Any, hwnd: int, x: int, y: int) -> None:
    point = _lparam(x, y)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0201, 0, point)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0202, 0, point)


def _send_key(user32: Any, hwnd: int, key_code: int) -> None:
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, key_code, 0)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, key_code, 0)


def _id_between(start: int, stop: int) -> Callable[[Mapping[str, object]], bool]:
    def predicate(row: Mapping[str, object]) -> bool:
        value = row.get("id")
        return isinstance(value, int) and start <= value < stop

    return predicate


@pytest.mark.skipif(sys.platform != "win32", reason="DataGrid native filter smoke requires Windows")
def test_datagrid_filtering_preserves_native_wgpu_context_and_filtered_navigation() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI DataGrid filter smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI filtered DataGrid", width=680, height=360))
    rows = [
        {"id": index, "name": f"Job {index}", "status": "Ready"}
        for index in range(200)
    ]
    grid = DataGrid(
        (
            DataGridColumn("id", "ID", width=90.0),
            DataGridColumn("name", "Name", width=240.0),
            DataGridColumn("status", "Status", width=140.0),
        ),
        rows,
        key="native-filter-grid",
        bounds=Rect(24.0, 24.0, 520.0, 240.0),
        row_height=30.0,
        header_height=40.0,
        selection_mode="multiple",
        accessible_name="Native filtered workload table",
    )
    runtime = mount(window, grid)
    filter_events = []
    grid.on("filter_changed", filter_events.append)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        grid.sort_by("id", descending=True)
        grid.set_filter(_id_between(190, 200))
        assert grid.is_filtered is True
        assert grid.source_row_count == 200
        assert len(grid.rows) == 10
        assert [row["id"] for row in grid.rows] == list(range(199, 189, -1))
        assert filter_events[-1].data["active"] is True
        assert filter_events[-1].data["visible_count"] == 10
        assert filter_events[-1].data["source_count"] == 200

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        row_nodes = [
            node
            for node in window.scene.walk()
            if node.key.startswith("native-filter-grid:row:")
            and node.kind is SceneNodeKind.RECTANGLE
        ]
        assert len(row_nodes) <= 8

        _send_click(
            user32,
            hwnd,
            max(1, round(170.0 * window.scale)),
            max(1, round(82.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is grid
        assert grid.selected_index == 0
        assert grid.selected_row is not None
        assert grid.selected_row["id"] == 199

        _send_key(user32, hwnd, 0x23)
        app.process_events()
        assert grid.selected_index == 9
        assert grid.selected_row is not None
        assert grid.selected_row["id"] == 190
        assert grid.scroll_offset == pytest.approx(100.0)

        grid.set_filter(_id_between(195, 200))
        assert len(grid.rows) == 5
        assert grid.selected_index is None
        assert grid.selected_rows == ()
        assert grid.scroll_offset == 0.0
        assert grid.source_row_count == 200

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        visible_text = {
            node.text
            for node in window.scene.walk()
            if node.kind is SceneNodeKind.TEXT and node.text is not None
        }
        assert "Job 199" in visible_text
        assert "Job 195" in visible_text
        assert "Job 194" not in visible_text

        grid.clear_filter()
        assert grid.is_filtered is False
        assert grid.source_row_count == 200
        assert len(grid.rows) == 200
        assert grid.rows[0]["id"] == 199
        assert filter_events[-1].data["active"] is False
        assert filter_events[-1].data["visible_count"] == 200
        assert runtime.generation > 1
    finally:
        app.stop()
