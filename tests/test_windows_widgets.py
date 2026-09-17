import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Component, Input, PasswordInput, TextArea, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


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


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_retained_text_inputs_route_real_win32_text_and_reuse_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI core widget smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI core widgets", width=620, height=360))
    root = Component("root")
    username = Input(
        key="username",
        bounds=Rect(28.0, 30.0, 280.0, 48.0),
        placeholder="Username",
        accessible_name="Username",
    )
    password = PasswordInput(
        "secret",
        key="password",
        bounds=Rect(28.0, 96.0, 280.0, 48.0),
        accessible_name="Password",
    )
    notes = TextArea(
        "native\nwidgets",
        key="notes",
        bounds=Rect(28.0, 162.0, 420.0, 118.0),
        accessible_name="Notes",
    )
    root.add(username, password, notes)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        app.process_events()
        x = max(1, round(48.0 * window.scale))
        y = max(1, round(50.0 * window.scale))
        _user32().SendMessageW(
            ctypes.c_void_p(window.native_handle.value),
            0x0201,  # WM_LBUTTONDOWN
            0,
            _lparam(x, y),
        )
        app.process_events()
        assert window.focused_component is username

        for character in "SwirUI":
            _user32().SendMessageW(
                ctypes.c_void_p(window.native_handle.value),
                0x0102,  # WM_CHAR
                ord(character),
                0,
            )
        app.process_events()
        assert username.value == "SwirUI"

        rendered = app.render_pending(time.monotonic() + 1.0)
        assert rendered == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        username_text = next(
            node for node in window.scene.walk() if node.key == "username:text"
        )
        password_text = next(
            node for node in window.scene.walk() if node.key == "password:text"
        )
        assert username_text.kind is SceneNodeKind.TEXT
        assert username_text.text == "SwirUI"
        assert password_text.text == "••••••"
        assert password_text.text != password.value
        assert runtime.generation > 1
    finally:
        app.stop()
