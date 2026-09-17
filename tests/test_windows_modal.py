import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Button, Component, Modal, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Modal.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Modal native smoke requires Windows")
def test_modal_traps_real_win32_focus_and_reuses_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI Modal smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Modal", width=720, height=420))
    root = Component("root")
    background = Button(
        "Open modal",
        key="background-action",
        bounds=Rect(32.0, 32.0, 180.0, 48.0),
    )
    content = Component("dialog-content")
    accept = Button(
        "Accept",
        key="modal-accept",
        bounds=Rect(24.0, 92.0, 130.0, 44.0),
    )
    cancel = Button(
        "Cancel",
        key="modal-cancel",
        bounds=Rect(170.0, 92.0, 130.0, 44.0),
    )
    content.add(accept, cancel)
    modal = Modal(
        key="native-modal",
        bounds=Rect(0.0, 0.0, 720.0, 420.0),
        dialog_bounds=Rect(185.0, 105.0, 350.0, 180.0),
        content=content,
        initially_open=False,
        accessible_name="Native confirmation",
    )
    root.add(background, modal)
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
        _send_click(
            user32,
            hwnd,
            max(1, round(90.0 * window.scale)),
            max(1, round(54.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is background

        assert modal.show(reason="native-test") is True
        assert window.focused_component is accept
        opened_generation = runtime.generation

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, 0x09, 0)
        app.process_events()
        assert window.focused_component is cancel

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, 0x1B, 0)
        app.process_events()
        assert modal.is_open is False
        assert window.focused_component is background
        assert runtime.generation > opened_generation

        modal.show(reason="scrim-test")
        assert window.focused_component is accept
        _send_click(
            user32,
            hwnd,
            max(1, round(40.0 * window.scale)),
            max(1, round(40.0 * window.scale)),
        )
        app.process_events()
        assert modal.is_open is False
        assert window.focused_component is background

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert all(node.key != "native-modal" for node in window.scene.walk())
    finally:
        app.stop()
