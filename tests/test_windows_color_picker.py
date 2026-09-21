import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, ColorPicker, Panel, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.ColorPicker.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Color picker smoke requires Windows")
def test_color_picker_native_input_keeps_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI color picker smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Color Picker", width=760, height=500))

    picker = ColorPicker(
        bounds=Rect(80.0, 70.0, 600.0, 330.0),
        value=Color.from_hex("#0088FFFF"),
        key="native-color-picker",
    )
    root = Panel(bounds=Rect(0.0, 0.0, 760.0, 500.0), key="color-picker-root")
    root.add(picker)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        hue_track = picker.track_bounds("hue")
        _send_click(
            user32,
            hwnd,
            round((hue_track.x + hue_track.width * 0.72) * window.scale),
            round((hue_track.y + hue_track.height * 0.5) * window.scale),
        )
        app.process_events()
        assert window.focused_component is picker
        assert picker.active_channel == "hue"
        hue_after_click = picker.channel_value("hue")

        _send_key(user32, hwnd, 0x27)
        app.process_events()
        assert picker.channel_value("hue") > hue_after_click

        saturation_track = picker.track_bounds("saturation")
        _send_click(
            user32,
            hwnd,
            round((saturation_track.x + saturation_track.width * 0.35) * window.scale),
            round((saturation_track.y + saturation_track.height * 0.5) * window.scale),
        )
        app.process_events()
        assert picker.active_channel == "saturation"
        assert picker.channel_value("saturation") == pytest.approx(0.35, abs=0.02)

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-color-picker:preview" in scene_keys
        assert "native-color-picker:thumb:hue" in scene_keys
        assert "native-color-picker:thumb:alpha" in scene_keys
        assert runtime.generation > 1
    finally:
        app.stop()
