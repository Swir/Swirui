import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, NavigationItem, NavigationRail, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.NavigationRail.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="NavigationRail native smoke requires Windows")
def test_navigation_rail_native_pointer_keyboard_keeps_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI NavigationRail smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI NavigationRail", width=640, height=420))

    rail = NavigationRail(
        (
            NavigationItem("home", "Home", "HM"),
            NavigationItem("disabled", "Disabled", "DS", disabled=True),
            NavigationItem("settings", "Settings", "ST"),
        ),
        bounds=Rect(24.0, 24.0, 180.0, 240.0),
        key="native-navigation",
        expanded=True,
        item_height=48.0,
        accessible_name="Native navigation",
    )
    runtime = mount(window, rail)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        assert rail.selected_key == "home"
        _send_click(
            user32,
            hwnd,
            max(1, round(80.0 * window.scale)),
            max(1, round(144.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is rail
        assert rail.selected_key == "settings"

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-navigation:item:2:accent" in scene_keys

        _send_key(user32, hwnd, 0x26)
        app.process_events()
        assert rail.selected_key == "home"

        _send_key(user32, hwnd, 0x23)
        app.process_events()
        assert rail.selected_key == "settings"

        _send_key(user32, hwnd, 0x24)
        app.process_events()
        assert rail.selected_key == "home"
        assert renderer.persistent_context_count == initial_contexts

        snapshot = rail.accessibility_snapshot(focused=rail)
        assert [child.name for child in snapshot.children] == ["Home", "Disabled", "Settings"]
        assert snapshot.children[0].selected is True
        assert snapshot.children[1].enabled is False
        assert snapshot.children[2].selected is False
        assert runtime.generation > 1
    finally:
        app.stop()
