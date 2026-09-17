import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Checkbox, Component, Input, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.CoreWidgets.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Core widget GPU smoke requires Windows")
def test_core_widgets_route_real_win32_text_and_pointer_input_through_wgpu() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI 0.4 widget gate", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI 0.4 widget gate", width=520, height=260))
    root = Component("root")
    field = Input(
        key="name",
        bounds=Rect(32.0, 36.0, 260.0, 48.0),
        placeholder="Name",
    )
    checkbox = Checkbox(
        "Enable effects",
        key="effects",
        bounds=Rect(32.0, 112.0, 210.0, 36.0),
    )
    root.add(field, checkbox)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert window.scene is not None

        user32 = _user32()
        hwnd = ctypes.c_void_p(window.native_handle.value)
        field_x = max(1, round(56 * window.scale))
        field_y = max(1, round(56 * window.scale))
        user32.SendMessageW(hwnd, 0x0201, 0, _lparam(field_x, field_y))
        app.process_events()
        assert window.focused_component is field

        user32.SendMessageW(hwnd, 0x0102, ord("A"), 0)
        app.process_events()
        assert field.value == "A"
        assert runtime.generation >= 3

        rendered = app.render_pending(time.monotonic() + 1.0)
        assert rendered == 1
        assert renderer.persistent_context_count == 1
        assert renderer.last_text_count >= 1

        check_x = max(1, round(46 * window.scale))
        check_y = max(1, round(128 * window.scale))
        pointer = _lparam(check_x, check_y)
        user32.SendMessageW(hwnd, 0x0201, 0, pointer)
        user32.SendMessageW(hwnd, 0x0202, 0, pointer)
        app.process_events()
        assert checkbox.checked is True
        assert window.focused_component is checkbox

        rendered = app.render_pending(time.monotonic() + 1.0)
        assert rendered == 1
        assert renderer.persistent_context_count == 1
        assert window.scene is not None
        assert any(node.key == "effects:mark" for node in window.scene.walk())
    finally:
        app.stop()
        assert runtime.mounted is False
