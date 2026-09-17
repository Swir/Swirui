import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import (
    App,
    Button,
    CrossAxisAlignment,
    Dock,
    DockSide,
    Flow,
    Grid,
    Insets,
    Overlay,
    OverlayAnchor,
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


@pytest.mark.skipif(sys.platform != "win32", reason="Layout native smoke requires Windows")
def test_dock_flow_overlay_route_input_in_real_win32_wgpu_session() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI advanced layout smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Dock + Flow + Overlay", width=760, height=420))

    toolbar = Flow(
        key="native-flow",
        bounds=Rect(0.0, 0.0, 500.0, 48.0),
        padding=Insets.symmetric(horizontal=8.0, vertical=4.0),
        spacing=12.0,
        wrap=False,
    )
    toolbar.add(
        Button("One", key="flow-one", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
        Button("Two", key="flow-two", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
    )
    sidebar = Button("Sidebar", key="dock-side", bounds=Rect(0.0, 0.0, 140.0, 80.0))
    action = Button("Run", key="overlay-action", bounds=Rect(0.0, 0.0, 140.0, 46.0))
    overlay = Overlay(key="native-overlay", bounds=Rect(0.0, 0.0, 1.0, 1.0))
    overlay.add_overlay(
        action,
        anchor=OverlayAnchor.BOTTOM_RIGHT,
        offset_x=-12.0,
        offset_y=-12.0,
    )
    dock = Dock(
        key="native-dock",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=24.0,
    )
    dock.add_docked(toolbar, DockSide.TOP)
    dock.add_docked(sidebar, DockSide.LEFT)
    dock.add_docked(overlay, DockSide.FILL)
    runtime = mount(window, dock)
    clicks: list[Event] = []
    action.on("click", clicks.append)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert window.scene is not None

        assert dock.bounds == Rect(0.0, 0.0, 760.0, 420.0)
        assert toolbar.bounds == Rect(24.0, 24.0, 712.0, 48.0)
        assert sidebar.bounds == Rect(24.0, 72.0, 140.0, 324.0)
        assert overlay.bounds == Rect(164.0, 72.0, 572.0, 324.0)
        assert action.bounds == Rect(584.0, 338.0, 140.0, 46.0)

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

        initial_contexts = renderer.persistent_context_count
        toolbar.spacing = 20.0
        assert runtime.generation > 1
        app.invalidate(window)
        frame_time = time.monotonic() + 2.0
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.frames_rendered >= 2
    finally:
        app.stop()
