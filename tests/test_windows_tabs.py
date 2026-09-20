import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Panel, TabItem, Tabs, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Tabs.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Tabs native smoke requires Windows")
def test_tabs_native_pointer_keyboard_and_pages_keep_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI Tabs smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Tabs", width=720, height=400))

    overview = Panel(
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        key="overview-page",
        accessible_name="Overview page",
    )
    disabled = Panel(
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        key="disabled-page",
        accessible_name="Disabled page",
    )
    settings = Panel(
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        key="settings-page",
        accessible_name="Settings page",
    )
    tabs = Tabs(
        (
            TabItem("overview", "Overview", overview),
            TabItem("disabled", "Disabled", disabled, disabled=True),
            TabItem("settings", "Settings", settings),
        ),
        bounds=Rect(24.0, 24.0, 540.0, 260.0),
        key="native-tabs",
        header_height=44.0,
        accessible_name="Native workspace tabs",
    )
    runtime = mount(window, tabs)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        assert tabs.selected_key == "overview"
        assert overview.visible is True
        assert disabled.visible is False
        assert settings.visible is False

        _send_click(
            user32,
            hwnd,
            max(1, round(474.0 * window.scale)),
            max(1, round(46.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is tabs
        assert tabs.selected_key == "settings"
        assert overview.visible is False
        assert settings.visible is True

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "settings-page" in scene_keys
        assert "overview-page" not in scene_keys
        assert "disabled-page" not in scene_keys

        _send_key(user32, hwnd, 0x25)
        app.process_events()
        assert tabs.selected_key == "overview"

        _send_key(user32, hwnd, 0x23)
        app.process_events()
        assert tabs.selected_key == "settings"

        _send_key(user32, hwnd, 0x24)
        app.process_events()
        assert tabs.selected_key == "overview"
        assert renderer.persistent_context_count == initial_contexts

        snapshot = tabs.accessibility_snapshot(focused=tabs)
        tab_nodes = [
            child
            for child in snapshot.children
            if child.name in {"Overview", "Disabled", "Settings"}
        ]
        assert [child.name for child in tab_nodes] == ["Overview", "Disabled", "Settings"]
        assert tab_nodes[0].selected is True
        assert tab_nodes[1].enabled is False
        assert tab_nodes[2].selected is False
        assert any(child.name == "Overview page" for child in snapshot.children)
        assert runtime.generation > 1
    finally:
        app.stop()
