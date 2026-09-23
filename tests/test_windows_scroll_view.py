import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Button, Component, DataGrid, DataGridColumn, ScrollView, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.ScrollView.{id(backend):x}"
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


def _send_drag(user32: Any, hwnd: int, start_x: int, y: int, end_x: int) -> None:
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0201, 0, _lparam(start_x, y))
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0x0001, _lparam(end_x, y))
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0202, 0, _lparam(end_x, y))


def _send_key(user32: Any, hwnd: int, key_code: int) -> None:
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, key_code, 0)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, key_code, 0)


def _render_due_frame(app: App) -> int:
    """Advance only to the scheduler's real next deadline for deterministic smoke tests."""

    now = time.monotonic()
    wait = app.seconds_until_next_frame(now)
    assert wait is not None
    return app.render_pending(now + wait + 1.0e-6)


@pytest.mark.skipif(sys.platform != "win32", reason="ScrollView native smoke requires Windows")
def test_scroll_view_routes_scrolled_content_in_real_win32_wgpu_session() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI ScrollView smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI ScrollView", width=620, height=360))
    root = Component("root")
    scroll = ScrollView(
        key="native-scroll",
        bounds=Rect(24.0, 24.0, 320.0, 220.0),
        content_height=560.0,
        accessible_name="Native scrolling viewport",
    )
    deep_button = Button(
        "Scrolled GPU action",
        key="deep-action",
        bounds=Rect(24.0, 260.0, 190.0, 44.0),
    )
    scroll.add(deep_button)
    root.add(scroll)
    runtime = mount(window, root)
    clicks = []
    deep_button.on("click", clicks.append)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        app.process_events()
        _send_click(
            user32,
            hwnd,
            max(1, round(300.0 * window.scale)),
            max(1, round(64.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is scroll

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, 0x22, 0)
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, 0x22, 0)
        app.process_events()
        assert scroll.scroll_y == 196.0
        assert runtime.generation > 1

        button_x = max(1, round(72.0 * window.scale))
        button_y = max(1, round(110.0 * window.scale))
        _send_click(user32, hwnd, button_x, button_y)
        app.process_events()
        assert window.focused_component is deep_button
        assert len(clicks) == 1

        app.invalidate(window)
        assert _render_due_frame(app) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        viewport_node = next(
            node for node in window.scene.walk() if node.key == "native-scroll"
        )
        button_node = next(
            node for node in window.scene.walk() if node.key == "deep-action"
        )
        assert viewport_node.clip_to_bounds is True
        assert button_node.kind is SceneNodeKind.RECTANGLE
        assert button_node.bounds == Rect(48.0, 88.0, 190.0, 44.0)
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="DataGrid native smoke requires Windows")
def test_datagrid_virtualization_editing_and_keyboard_in_real_win32_wgpu_session() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI DataGrid smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI DataGrid", width=680, height=360))
    rows = [
        {"id": index, "name": f"Job {index}", "status": "Ready"}
        for index in range(200)
    ]
    grid = DataGrid(
        (
            DataGridColumn("id", "ID", width=80.0, min_width=60.0, max_width=140.0),
            DataGridColumn("name", "Name", width=240.0),
            DataGridColumn("status", "Status", width=140.0),
        ),
        rows,
        key="native-grid",
        bounds=Rect(24.0, 24.0, 520.0, 240.0),
        row_height=30.0,
        header_height=40.0,
        selection_mode="multiple",
        editable_columns=("name", "status"),
    )
    runtime = mount(window, grid)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        header_y = max(1, round(44.0 * window.scale))
        separator_x = max(1, round(104.0 * window.scale))
        resize_end_x = max(1, round(134.0 * window.scale))
        _send_drag(user32, hwnd, separator_x, header_y, resize_end_x)
        app.process_events()
        assert grid.columns[0].resolved_width == pytest.approx(110.0)

        header_x = max(1, round(54.0 * window.scale))
        _send_click(user32, hwnd, header_x, header_y)
        _send_click(user32, hwnd, header_x, header_y)
        app.process_events()
        assert grid.sort_column_key == "id"
        assert grid.sort_descending is True
        assert grid.rows[0]["id"] == 199

        _send_click(
            user32,
            hwnd,
            max(1, round(190.0 * window.scale)),
            max(1, round(82.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is grid
        assert grid.selected_index == 0
        assert grid.selected_row is not None
        assert grid.selected_row["id"] == 199
        assert grid.active_cell is not None
        assert grid.active_cell[1] == "name"

        _send_key(user32, hwnd, 0x71)
        app.process_events()
        assert grid.editing_cell == (0, "name", "Job 199")

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0102, ord("!"), 0)
        app.process_events()
        assert grid.editing_cell == (0, "name", "Job 199!")

        app.invalidate(window)
        assert _render_due_frame(app) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        editor_text = next(
            node for node in window.scene.walk() if node.key == "native-grid:editor:text"
        )
        assert editor_text.kind is SceneNodeKind.TEXT
        assert editor_text.text == "Job 199!│"

        _send_key(user32, hwnd, 0x0D)
        app.process_events()
        assert grid.is_editing is False
        assert grid.rows[0]["name"] == "Job 199!"

        _send_key(user32, hwnd, 0x28)
        _send_key(user32, hwnd, 0x28)
        app.process_events()
        assert grid.selected_index == 2
        assert grid.scroll_offset == 0.0

        _send_key(user32, hwnd, 0x23)
        app.process_events()
        assert grid.selected_index == 199
        assert grid.scroll_offset == 5800.0
        assert 199 in grid.visible_row_range

        app.invalidate(window)
        assert _render_due_frame(app) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        row_nodes = [
            node
            for node in window.scene.walk()
            if node.key.startswith("native-grid:row:")
            and node.kind is SceneNodeKind.RECTANGLE
        ]
        assert len(row_nodes) <= 8
        assert any(node.key == "native-grid:row:199" for node in row_nodes)
        assert runtime.generation > 1
    finally:
        app.stop()
