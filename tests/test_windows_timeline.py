import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Timeline, TimelineItem, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Timeline.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Timeline smoke requires Windows")
def test_timeline_native_input_keeps_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI timeline smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Timeline", width=760, height=460))
    timeline = Timeline(
        (
            TimelineItem("plan", "Plan", "09:00", "Define the contract."),
            TimelineItem("build", "Build", "10:30", disabled=True),
            TimelineItem("verify", "Verify", "12:00", "Run qualification."),
        ),
        bounds=Rect(80.0, 60.0, 520.0, 240.0),
        key="native-timeline",
    )
    activated: list[object] = []
    timeline.on("item_activated", lambda event: activated.append(event.data["key"]))
    runtime = mount(window, timeline)

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
            max(1, round(255.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is timeline
        assert timeline.selected_item is not None
        assert timeline.selected_item.key == "verify"

        _send_key(user32, hwnd, 0x26)
        app.process_events()
        assert timeline.selected_item is not None
        assert timeline.selected_item.key == "plan"

        _send_key(user32, hwnd, 0x0D)
        app.process_events()
        assert activated == ["plan"]

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-timeline:axis" in scene_keys
        assert "native-timeline:item:0:marker" in scene_keys
        assert runtime.generation > 1
    finally:
        app.stop()
