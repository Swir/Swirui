import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Badge, Chip, Component, Tooltip, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.StatusWidgets.{id(backend):x}"
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
def test_badge_chip_tooltip_route_real_win32_hover_and_reuse_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI status widget smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI status widgets", width=560, height=280))
    root = Component("root")
    badge = Badge("ALPHA", key="native-badge", bounds=Rect(28.0, 30.0, 90.0, 30.0))
    chip = Chip("GPU renderer", key="native-chip", bounds=Rect(28.0, 92.0, 160.0, 38.0))
    tooltip = Tooltip(
        "Native retained tooltip",
        target=chip,
        key="native-tooltip",
        bounds=Rect(28.0, 144.0, 210.0, 36.0),
    )
    root.add(badge, chip, tooltip)
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
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0200,
            0,
            _lparam(
                max(1, round(80.0 * window.scale)),
                max(1, round(110.0 * window.scale)),
            ),
        )
        app.process_events()
        assert tooltip.visible is True
        assert runtime.generation > 1

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert next(
            node for node in window.scene.walk() if node.key == "native-badge:content"
        ).kind is SceneNodeKind.TEXT
        assert next(
            node for node in window.scene.walk() if node.key == "native-chip:content"
        ).kind is SceneNodeKind.TEXT
        assert next(
            node for node in window.scene.walk() if node.key == "native-tooltip:content"
        ).kind is SceneNodeKind.TEXT
    finally:
        app.stop()
