import ctypes
import sys
import time
from datetime import date
from datetime import time as dt_time
from typing import Any

import pytest

from swirui import App, Calendar, DatePicker, Panel, TimePicker, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.DateTime.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Date/time smoke requires Windows")
def test_calendar_and_pickers_native_input_keep_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI date/time smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(
        Window(title="SwirUI Date and Time", width=840, height=650)
    )

    calendar = Calendar(
        bounds=Rect(80.0, 40.0, 560.0, 360.0),
        selected_date=date(2026, 9, 21),
        key="native-calendar",
    )
    date_picker = DatePicker(
        bounds=Rect(80.0, 430.0, 330.0, 64.0),
        value=date(2026, 9, 21),
        key="native-date-picker",
    )
    time_picker = TimePicker(
        bounds=Rect(430.0, 430.0, 210.0, 64.0),
        value=dt_time(10, 30),
        minute_step=5,
        key="native-time-picker",
    )
    root = Panel(
        bounds=Rect(0.0, 0.0, 840.0, 650.0),
        key="date-time-root",
    )
    root.add(calendar, date_picker, time_picker)
    runtime = mount(window, root)

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
            round(225.0 * window.scale),
            round(273.0 * window.scale),
        )
        app.process_events()
        assert window.focused_component is calendar
        selected_after_click = calendar.selected_date

        _send_key(user32, hwnd, 0x27)
        app.process_events()
        assert calendar.selected_date > selected_after_click

        _send_click(
            user32,
            hwnd,
            round(350.0 * window.scale),
            round(460.0 * window.scale),
        )
        app.process_events()
        assert window.focused_component is date_picker
        before_date = date_picker.value
        _send_key(user32, hwnd, 0x26)
        app.process_events()
        assert date_picker.value != before_date

        _send_click(
            user32,
            hwnd,
            round(550.0 * window.scale),
            round(460.0 * window.scale),
        )
        app.process_events()
        assert window.focused_component is time_picker
        before_time = time_picker.value
        _send_key(user32, hwnd, 0x26)
        app.process_events()
        assert time_picker.value != before_time

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-calendar:month-title" in scene_keys
        assert "native-date-picker:segment:2:value" in scene_keys
        assert "native-time-picker:segment:1:value" in scene_keys
        assert runtime.generation > 1
    finally:
        app.stop()
