from __future__ import annotations

from collections.abc import Callable

import pytest

from swirui import Component, DataGrid, DataGridColumn, ScrollView, Window, mount
from swirui.core import Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Rect


def _grid(*, y: float = 20.0) -> DataGrid:
    return DataGrid(
        (
            DataGridColumn("id", "ID", width=120.0),
            DataGridColumn("name", "Name", width=220.0),
        ),
        tuple({"id": index, "name": f"Row {index}"} for index in range(100)),
        key="grid",
        bounds=Rect(20.0, y, 220.0, 120.0),
        row_height=30.0,
        header_height=36.0,
    )


def test_standalone_scrollview_consumes_precise_native_delta_through_component_route() -> None:
    window = Window(width=360, height=240)
    window.scale = 2.0
    root = Component("root")
    scroll = ScrollView(
        key="scroll",
        bounds=Rect(20.0, 20.0, 180.0, 100.0),
        content_height=420.0,
    )
    root.add(scroll)
    runtime = mount(window, root)
    forwarded: list[Event] = []
    unsubscribe: Callable[[], None] = window.on("pointer_scroll", forwarded.append)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            NativeWindowHandle(1),
            x=120.0,
            y=120.0,
            delta_y=17.25,
        )
    )

    assert scroll.scroll_y == pytest.approx(17.25)
    assert forwarded == []
    unsubscribe()
    runtime.unmount()


def test_shift_wheel_maps_once_to_scrollview_horizontal_axis() -> None:
    window = Window(width=360, height=240)
    scroll = ScrollView(
        key="scroll",
        bounds=Rect(20.0, 20.0, 180.0, 100.0),
        content_width=420.0,
        content_height=100.0,
    )
    runtime = mount(window, scroll)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            NativeWindowHandle(1),
            x=80.0,
            y=60.0,
            delta_y=31.5,
            shift=True,
        )
    )

    assert scroll.scroll_x == pytest.approx(31.5)
    assert scroll.scroll_y == 0.0
    runtime.unmount()


def test_nested_scrollviews_chain_only_residual_to_outer_and_window_fallback() -> None:
    window = Window(width=360, height=240)
    root = Component("root")
    outer = ScrollView(
        key="outer",
        bounds=Rect(0.0, 0.0, 220.0, 140.0),
        content_height=160.0,
        scroll_y=15.0,
    )
    inner = ScrollView(
        key="inner",
        bounds=Rect(20.0, 20.0, 180.0, 100.0),
        content_height=200.0,
        scroll_y=90.0,
    )
    outer.add(inner)
    root.add(outer)
    runtime = mount(window, root)
    forwarded: list[Event] = []
    unsubscribe: Callable[[], None] = window.on("pointer_scroll", forwarded.append)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            NativeWindowHandle(1),
            x=60.0,
            y=60.0,
            delta_y=48.0,
        )
    )

    assert inner.scroll_y == pytest.approx(inner.max_scroll_y)
    assert outer.scroll_y == pytest.approx(outer.max_scroll_y)
    assert len(forwarded) == 1
    residual = forwarded[0].data["event"]
    assert isinstance(residual, PlatformEvent)
    assert residual.delta_y == pytest.approx(33.0)
    original = forwarded[0].data["original_event"]
    assert isinstance(original, PlatformEvent)
    assert original.delta_y == pytest.approx(48.0)

    unsubscribe()
    runtime.unmount()


def test_datagrid_bubbles_partial_wheel_delta_to_scrollview_without_double_scroll() -> None:
    window = Window(width=420, height=260)
    parent = ScrollView(
        key="parent",
        bounds=Rect(0.0, 0.0, 300.0, 180.0),
        content_height=200.0,
        scroll_y=10.0,
    )
    grid = _grid(y=20.0)
    parent.add(grid)
    runtime = mount(window, parent)

    grid.scroll_by(100_000.0)
    grid_max = grid.scroll_offset
    grid.scroll_by(-12.0)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_SCROLL,
            NativeWindowHandle(1),
            x=80.0,
            y=80.0,
            delta_y=26.0,
        )
    )

    assert grid.scroll_offset == pytest.approx(grid_max)
    assert parent.scroll_y == pytest.approx(20.0)
    runtime.unmount()
