import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, CommandItem, Ribbon, RibbonGroup, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.CommandSurfaces.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Command surface native smoke requires Windows")
def test_ribbon_native_pointer_keeps_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI command surface smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Ribbon", width=720, height=360))

    ribbon = Ribbon(
        (
            RibbonGroup(
                "home",
                "Home",
                (CommandItem("paste", "Paste"), CommandItem("copy", "Copy")),
            ),
            RibbonGroup(
                "view",
                "View",
                (CommandItem("zoom", "Zoom"), CommandItem("grid", "Grid")),
            ),
        ),
        bounds=Rect(24.0, 24.0, 520.0, 120.0),
        key="native-ribbon",
        tab_width=112.0,
        command_width=108.0,
    )
    runtime = mount(window, ribbon)

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
            max(1, round(160.0 * window.scale)),
            max(1, round(40.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is ribbon
        assert ribbon.selected_key == "view"

        _send_click(
            user32,
            hwnd,
            max(1, round(170.0 * window.scale)),
            max(1, round(88.0 * window.scale)),
        )
        app.process_events()
        assert ribbon.active_command is not None
        assert ribbon.active_command.key == "grid"

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-ribbon:group:1" in scene_keys
        assert "native-ribbon:command:1" in scene_keys
        assert runtime.generation > 1
    finally:
        app.stop()
