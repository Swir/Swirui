import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import (
    App,
    Button,
    ConstraintLayout,
    ConstraintSpec,
    Dock,
    DockPanel,
    Window,
    mount,
)
from swirui.core import Event
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AdvancedLayout.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Advanced layout smoke requires Windows")
def test_dock_and_constraint_layout_keep_routed_input_and_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI advanced layout smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Dock + Constraint", width=760, height=420))

    sidebar = Button("Sidebar", key="sidebar", bounds=Rect(0.0, 0.0, 150.0, 48.0))
    action = Button("Action", key="action", bounds=Rect(0.0, 0.0, 140.0, 48.0))
    content = ConstraintLayout(
        key="content-layout",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
    )
    content.add(action)
    content.set_constraints(
        action,
        ConstraintSpec(right=32.0, bottom=28.0, width=160.0, height=52.0),
    )

    root = DockPanel(
        key="root-dock",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=24.0,
        spacing=16.0,
    )
    root.add(sidebar, content)
    root.set_dock(sidebar, Dock.LEFT)
    runtime = mount(window, root)
    clicks: list[Event] = []
    action.on("click", clicks.append)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        assert root.bounds == Rect(0.0, 0.0, 760.0, 420.0)
        assert sidebar.bounds == Rect(24.0, 24.0, 150.0, 372.0)
        assert content.bounds == Rect(174.0, 24.0, 562.0, 372.0)
        assert action.bounds == Rect(544.0, 316.0, 160.0, 52.0)

        target_x = round((action.bounds.x + action.bounds.width * 0.5) * window.scale)
        target_y = round((action.bounds.y + action.bounds.height * 0.5) * window.scale)
        hwnd = window.native_handle.value
        user32 = _user32()
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0201,
            0x0001,
            _lparam(target_x, target_y),
        )
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0202,
            0,
            _lparam(target_x, target_y),
        )
        app.process_events()

        assert len(clicks) == 1
        assert window.focused_component is action

        content.set_constraints(
            action,
            ConstraintSpec(left=40.0, top=36.0, width=180.0, height=56.0),
        )
        assert runtime.generation > 1
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert action.bounds == Rect(214.0, 60.0, 180.0, 56.0)
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.frames_rendered >= 2
    finally:
        app.stop()
