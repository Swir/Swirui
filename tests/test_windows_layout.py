import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import (
    App,
    Button,
    CrossAxisAlignment,
    Grid,
    Insets,
    Row,
    Window,
    Wrap,
    mount,
)
from swirui.core import Event
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Layout.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Layout native smoke requires Windows")
def test_row_layout_routes_arranged_input_in_real_win32_wgpu_session() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI layout smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Row layout", width=720, height=360))
    first = Button("Primary", key="primary", bounds=Rect(0.0, 0.0, 160.0, 48.0))
    second = Button("Secondary", key="secondary", bounds=Rect(0.0, 0.0, 160.0, 48.0))
    first.set_layout_grow(1.0)
    second.set_layout_grow(2.0)
    row = Row(
        key="native-row",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=Insets.symmetric(horizontal=32.0, vertical=120.0),
        spacing=16.0,
        cross_alignment=CrossAxisAlignment.STRETCH,
    )
    row.add(first, second)
    runtime = mount(window, row)
    clicks: list[Event] = []
    second.on("click", clicks.append)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        assert row.bounds == Rect(0.0, 0.0, 720.0, 360.0)
        assert first.bounds.x == pytest.approx(32.0)
        assert second.bounds.x > first.bounds.right
        assert first.bounds.height == pytest.approx(120.0)
        assert second.bounds.right == pytest.approx(688.0)

        target_x = round((second.bounds.x + second.bounds.width * 0.5) * window.scale)
        target_y = round((second.bounds.y + second.bounds.height * 0.5) * window.scale)
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
        assert window.focused_component is second

        row.spacing = 28.0
        assert runtime.generation > 1
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.frames_rendered >= 2
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Layout native smoke requires Windows")
def test_grid_and_wrap_compile_in_real_win32_wgpu_session() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI panel layout smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Grid + Wrap", width=760, height=420))

    wrapped = Wrap(
        key="native-wrap",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        spacing=8.0,
        run_spacing=6.0,
    )
    wrapped.add(
        Button("One", key="wrap-one", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
        Button("Two", key="wrap-two", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
        Button("Three", key="wrap-three", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
    )
    grid = Grid(
        key="native-grid",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        columns=2,
        column_weights=(1.0, 2.0),
        column_spacing=18.0,
        padding=24.0,
    )
    grid.add(
        Button("Sidebar", key="grid-side", bounds=Rect(0.0, 0.0, 120.0, 48.0)),
        wrapped,
    )
    mount(window, grid)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert window.scene is not None

        nodes = {node.key: node for node in window.scene.walk()}
        assert nodes["native-grid"].bounds == Rect(0.0, 0.0, 760.0, 420.0)
        assert nodes["grid-side"].bounds.x == pytest.approx(24.0)
        assert nodes["native-wrap"].bounds.x > nodes["grid-side"].bounds.right
        assert nodes["wrap-one"].bounds.x == pytest.approx(nodes["native-wrap"].bounds.x)
        assert nodes["wrap-three"].bounds.y >= nodes["wrap-one"].bounds.y

        initial_contexts = renderer.persistent_context_count
        grid.column_weights = (2.0, 1.0)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
    finally:
        app.stop()
