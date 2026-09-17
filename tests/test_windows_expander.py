import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import Accordion, App, Expander, Label, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Expander.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="expander smoke requires Windows")
def test_expander_accordion_routes_real_win32_input_and_reuses_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI expander smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI retained accordion", width=680, height=360))

    first_content = Label(
        "First retained content",
        key="first-content",
        bounds=Rect(48.0, 90.0, 300.0, 28.0),
    )
    second_content = Label(
        "Second retained content",
        key="second-content",
        bounds=Rect(48.0, 180.0, 300.0, 28.0),
    )
    first = Expander(
        "First section",
        key="first-expander",
        bounds=Rect(28.0, 28.0, 520.0, 44.0),
        content=first_content,
        expanded=True,
    )
    second = Expander(
        "Second section",
        key="second-expander",
        bounds=Rect(28.0, 118.0, 520.0, 44.0),
        content=second_content,
    )
    accordion = Accordion(
        first,
        second,
        key="native-accordion",
        require_one=True,
        accessible_name="Native accordion",
    )
    runtime = mount(window, accordion)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        app.process_events()
        assert window.scene is not None
        assert next(
            node for node in window.scene.walk() if node.key == "first-content"
        ).kind is SceneNodeKind.TEXT
        assert all(node.key != "second-content" for node in window.scene.walk())

        _send_click(
            user32,
            hwnd,
            max(1, round(120.0 * window.scale)),
            max(1, round(140.0 * window.scale)),
        )
        app.process_events()

        assert window.focused_component is second
        assert second.expanded is True
        assert first.expanded is False
        assert runtime.generation > 1

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert next(
            node for node in window.scene.walk() if node.key == "second-content"
        ).kind is SceneNodeKind.TEXT
        assert all(node.key != "first-content" for node in window.scene.walk())
        assert next(
            node for node in window.scene.walk() if node.key == "second-expander:indicator"
        ).text == "▾"
    finally:
        app.stop()
