from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from swirui import DataGrid, DataGridColumn, Window, mount
from swirui.core import Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Rect

if TYPE_CHECKING:
    from collections.abc import Callable


def _scroll_grid() -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=120.0),
            DataGridColumn("name", "Name", width=220.0),
            DataGridColumn("status", "Status", width=160.0),
        ),
        tuple(
            {
                "id": index,
                "name": f"Item {index}",
                "status": "Ready",
            }
            for index in range(100)
        ),
        key="scroll-grid",
        bounds=Rect(20.0, 20.0, 240.0, 130.0),
        row_height=30.0,
        header_height=40.0,
    )


def test_pointer_scroll_preserves_high_resolution_deltas() -> None:
    event = PlatformEvent(
        PlatformEventKind.POINTER_SCROLL,
        NativeWindowHandle(7),
        x=10.0,
        y=20.0,
        delta_x=3.25,
        delta_y=-7.5,
        shift=True,
    )

    assert event.delta_x == pytest.approx(3.25)
    assert event.delta_y == pytest.approx(-7.5)
    assert event.shift is True


def test_datagrid_consumes_vertical_and_horizontal_scroll_in_logical_dips() -> None:
    window = Window(width=480, height=240)
    window.scale = 2.0
    grid = _scroll_grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            handle,
            x=120.0,
            y=160.0,
            delta_y=37.5,
        )
    )
    assert grid.scroll_offset == pytest.approx(37.5)
    assert grid.horizontal_scroll_offset == 0.0

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            handle,
            x=120.0,
            y=160.0,
            delta_x=22.25,
            delta_y=11.5,
        )
    )
    assert grid.scroll_offset == pytest.approx(49.0)
    assert grid.horizontal_scroll_offset == pytest.approx(22.25)
    runtime.unmount()


def test_shift_wheel_maps_vertical_motion_to_horizontal_scroll() -> None:
    window = Window(width=480, height=240)
    grid = _scroll_grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            handle,
            x=100.0,
            y=80.0,
            delta_y=48.0,
            shift=True,
        )
    )

    assert grid.scroll_offset == 0.0
    assert grid.horizontal_scroll_offset == pytest.approx(48.0)
    runtime.unmount()


def test_datagrid_scroll_chains_at_boundaries_and_unsubscribes_on_unmount() -> None:
    window = Window(width=480, height=240)
    grid = _scroll_grid()
    runtime = mount(window, grid)
    handle = NativeWindowHandle(1)
    forwarded: list[Event] = []
    unsubscribe: Callable[[], None] = window.on("pointer_scroll", forwarded.append)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            handle,
            x=100.0,
            y=80.0,
            delta_y=-48.0,
        )
    )
    assert grid.scroll_offset == 0.0
    assert len(forwarded) == 1

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            handle,
            x=100.0,
            y=80.0,
            delta_y=48.0,
        )
    )
    assert grid.scroll_offset == pytest.approx(48.0)
    assert len(forwarded) == 1

    runtime.unmount()
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            handle,
            x=100.0,
            y=80.0,
            delta_y=48.0,
        )
    )
    assert grid.scroll_offset == pytest.approx(48.0)
    assert len(forwarded) == 2
    unsubscribe()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="X11 normalization test")
def test_x11_scroll_buttons_normalize_to_backend_neutral_deltas() -> None:
    from swirui.platforms.base import NativeWindowSpec
    from swirui.platforms.linux import _ButtonPress, _XEvent
    from swirui.platforms.linux_scroll import LinuxX11PlatformBackend

    backend = object.__new__(LinuxX11PlatformBackend)
    handle = NativeWindowHandle(99)
    backend._windows = {
        handle: NativeWindowSpec(
            title="scroll",
            width=320,
            height=200,
            min_width=100,
            min_height=100,
        )
    }

    event = _XEvent()
    event.xbutton.type = _ButtonPress
    event.xbutton.window = handle.value
    event.xbutton.x = 23
    event.xbutton.y = 41
    event.xbutton.button = 5
    normalized = backend._normalize_event(event)

    assert len(normalized) == 1
    assert normalized[0].kind is PlatformEventKind.POINTER_SCROLL
    assert normalized[0].delta_x == 0.0
    assert normalized[0].delta_y == pytest.approx(48.0)
    assert normalized[0].x == pytest.approx(23.0)
    assert normalized[0].y == pytest.approx(41.0)


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 normalization test")
def test_win32_scroll_message_keeps_partial_wheel_motion() -> None:
    from swirui.platforms.base import NativeWindowSpec
    from swirui.platforms.windows_scroll import Win32PlatformBackend, _WM_MOUSEWHEEL

    backend = Win32PlatformBackend()
    backend.initialize()
    handle = backend.create_window(
        NativeWindowSpec(
            title="scroll",
            width=320,
            height=200,
            min_width=100,
            min_height=100,
        )
    )
    try:
        raw_delta = 30
        wparam = (raw_delta & 0xFFFF) << 16
        assert backend._wndproc(handle.value, _WM_MOUSEWHEEL, wparam, 0) == 0
        normalized = backend._events[-1]
        assert normalized.kind is PlatformEventKind.POINTER_SCROLL
        assert normalized.delta_x == 0.0
        assert normalized.delta_y == pytest.approx(-12.0)
    finally:
        backend.destroy_window(handle)
        backend.shutdown()
