import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Button, Component, SplitView, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.SplitView.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="SplitView native smoke requires Windows")
def test_split_view_resizes_panes_in_real_win32_wgpu_session() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI SplitView smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI SplitView", width=720, height=420))
    root = Component("root")
    split = SplitView(
        key="native-split",
        bounds=Rect(32.0, 32.0, 600.0, 280.0),
        first=Button(
            "Explorer pane",
            key="explorer-pane",
            bounds=Rect(20.0, 24.0, 180.0, 48.0),
        ),
        second=Button(
            "Editor pane",
            key="editor-pane",
            bounds=Rect(20.0, 24.0, 220.0, 48.0),
        ),
        split_ratio=0.45,
        divider_size=10.0,
        accessible_name="Workspace split",
    )
    root.add(split)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        app.process_events()
        divider = split.divider_bounds
        down_x = max(1, round((divider.x + divider.width * 0.5) * window.scale))
        down_y = max(1, round((divider.y + 70.0) * window.scale))
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0201,
            0x0001,
            _lparam(down_x, down_y),
        )
        app.process_events()
        assert window.focused_component is split
        assert split.dragging is True

        move_x = max(1, round(430.0 * window.scale))
        move_y = max(1, round(90.0 * window.scale))
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0200,
            0x0001,
            _lparam(move_x, move_y),
        )
        app.process_events()
        assert split.split_ratio > 0.6
        assert runtime.generation > 1

        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0202,
            0,
            _lparam(move_x, move_y),
        )
        app.process_events()
        assert split.dragging is False

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        divider_node = next(
            node
            for node in window.scene.walk()
            if node.key == "native-split" and node.kind is SceneNodeKind.RECTANGLE
        )
        editor = next(
            node for node in window.scene.walk() if node.key == "editor-pane"
        )
        assert divider_node.bounds == split.divider_bounds
        assert editor.bounds.x == pytest.approx(split.second_pane_bounds.x + 20.0)
    finally:
        app.stop()
