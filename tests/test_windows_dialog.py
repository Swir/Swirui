import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Button, Component, Dialog, DialogResult, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Dialog.{id(backend):x}"
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


def _send_key(user32: Any, hwnd: int, key_code: int) -> None:
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, key_code, 0)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, key_code, 0)


def _send_click(user32: Any, hwnd: int, x: int, y: int) -> None:
    point = _lparam(x, y)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0201, 0x0001, point)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0202, 0, point)


@pytest.mark.skipif(sys.platform != "win32", reason="Dialog native smoke requires Windows")
def test_modal_dialog_traps_real_win32_focus_and_reuses_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI Dialog smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Modal Dialog", width=700, height=420))

    root = Component("root", key="root")
    outside = Button(
        "Background action",
        key="background-action",
        bounds=Rect(28.0, 28.0, 190.0, 46.0),
    )
    background_clicks: list[bool] = []
    outside.on("click", lambda _event: background_clicks.append(True))
    dialog = Dialog(
        "Confirm action",
        key="native-dialog",
        bounds=Rect(0.0, 0.0, 700.0, 420.0),
        panel_bounds=Rect(170.0, 95.0, 360.0, 220.0),
    )
    cancel = Button(
        "Cancel",
        key="dialog-cancel",
        bounds=Rect(62.0, 142.0, 105.0, 42.0),
    )
    confirm = Button(
        "Confirm",
        key="dialog-confirm",
        bounds=Rect(190.0, 142.0, 105.0, 42.0),
    )
    dialog.add(cancel, confirm)
    root.add(outside, dialog)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()
        window.focus_component(outside)

        frame_time = time.monotonic() + 1.0
        dialog.open(window, initial_focus=cancel)
        assert window.focused_component is cancel
        assert runtime.generation > 1
        assert app.render_pending(frame_time) == 1
        frame_time += 1.0
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert any(node.key == "native-dialog:title" for node in window.scene.walk())
        assert any(node.key == "dialog-cancel" for node in window.scene.walk())
        assert any(node.key == "dialog-confirm" for node in window.scene.walk())
        first_open_generation = runtime.generation

        _send_key(user32, hwnd, 0x09)
        app.process_events()
        assert window.focused_component is confirm

        window.focus_component(outside)
        assert window.focused_component is cancel

        # Click the modal scrim directly over the underlying background button.
        # The dialog must dismiss while the covered button receives no click.
        scrim_x = max(1, round(40.0 * window.scale))
        scrim_y = max(1, round(50.0 * window.scale))
        _send_click(user32, hwnd, scrim_x, scrim_y)
        app.process_events()

        assert background_clicks == []
        assert dialog.result is DialogResult.DISMISSED
        assert dialog.is_open is False
        assert window.focused_component is outside
        assert runtime.generation > first_open_generation
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert all(node.key != "native-dialog:title" for node in window.scene.walk())
        assert all(node.key != "dialog-cancel" for node in window.scene.walk())
        assert all(node.key != "dialog-confirm" for node in window.scene.walk())
    finally:
        app.stop()
