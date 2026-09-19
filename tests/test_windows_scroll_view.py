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


def _send_key(user32: Any, hwnd: int, key_code: int) -> None:
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, key_code, 0)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, key_code, 0)


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
        assert app.render_pending(time.monotonic() + 1.0) == 1
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
def test_datagrid_virtualization_and_keyboard_selection_in_real_win32_wgpu_session() -> None:
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
            DataGridColumn("id", "ID", width=80.0),
            DataGridColumn("name", "Name", width=240.0),
            DataGridColumn("status", "Status", width=140.0),
        ),
        rows,
        key="native-grid",
        bounds=Rect(24.0, 24.0, 520.0, 240.0),
        row_height=30.0,
        header_height=40.0,
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

        _send_click(
            user32,
            hwnd,
            max(1, round(90.0 * window.scale)),
            max(1, round(82.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is grid
        assert grid.selected_index == 0

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
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        row_nodes = [
            node
            for node in window.scene.walk()
            if node.key.startswith("native-grid:row:") and ":cell:" not in node.key
        ]
        assert len(row_nodes) <= 8
        assert any(node.key == "native-grid:row:199" for node in row_nodes)
        assert runtime.generation > 1
    finally:
        app.stop()
