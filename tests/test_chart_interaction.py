from __future__ import annotations

import pytest

from swirui import AreaChart, BarChart, ChartPoint, ChartSeries, LineChart
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def _series() -> tuple[ChartSeries, ...]:
    return (
        ChartSeries(
            "downloads",
            "Downloads",
            tuple(
                ChartPoint(index, label, value)
                for index, (label, value) in enumerate(
                    (
                        ("Mon", 12.0),
                        ("Tue", 22.0),
                        ("Wed", 16.0),
                        ("Thu", 30.0),
                        ("Fri", 18.0),
                    )
                )
            ),
        ),
        ChartSeries(
            "installs",
            "Installs",
            tuple(
                ChartPoint(index, label, value)
                for index, (label, value) in enumerate(
                    (
                        ("Mon", 8.0),
                        ("Tue", 14.0),
                        ("Wed", 19.0),
                        ("Thu", 24.0),
                        ("Fri", 17.0),
                    )
                )
            ),
        ),
    )


def _native(
    kind: PlatformEventKind,
    *,
    x: float | None = None,
    y: float | None = None,
    delta_y: float = 0.0,
    button: PointerButton | None = None,
    key_code: int | None = None,
) -> PlatformEvent:
    return PlatformEvent(
        kind=kind,
        window=NativeWindowHandle(1),
        x=x,
        y=y,
        delta_y=delta_y,
        button=button,
        key_code=key_code,
    )


def test_cartesian_selection_is_public_stable_and_accessible() -> None:
    chart = LineChart(
        _series(),
        bounds=Rect(0.0, 0.0, 560.0, 280.0),
        key="interactive-line",
        title="Activity",
    )

    selection = chart.select_by_key("downloads", 1)
    scene = chart.build_scene_node()
    snapshot = chart.accessibility_snapshot()

    assert selection.series_index == 0
    assert selection.point_index == 1
    assert selection.label == "Tue"
    assert chart.selection == selection
    assert {node.key for node in scene.walk()} >= {
        "interactive-line:selection:halo",
        "interactive-line:selection:marker",
    }
    selected_node = snapshot.find("interactive-line:series:0:point:1")
    assert selected_node is not None
    assert selected_node.selected is True
    assert "selected Tue 22" in (snapshot.value_text or "")


def test_zoom_is_anchored_bounded_and_resettable() -> None:
    chart = AreaChart(
        _series(),
        bounds=Rect(0.0, 0.0, 600.0, 300.0),
        key="interactive-area",
    )
    full = chart.viewport

    zoomed = chart.zoom(2.0, anchor_x=0.75, anchor_y=0.25)

    assert chart.zoom_level == pytest.approx(2.0)
    assert zoomed.x_min > full.x_min
    assert zoomed.x_max <= full.x_max
    assert zoomed.y_min >= full.y_min
    assert zoomed.y_max < full.y_max
    assert zoomed.x_max - zoomed.x_min == pytest.approx(
        (full.x_max - full.x_min) / 2.0
    )

    chart.zoom(0.0001)
    assert chart.viewport == full
    assert chart.zoom_level == 1.0

    chart.zoom(2.0)
    chart.reset_zoom()
    assert chart.viewport == full

    with pytest.raises(ValueError, match="greater than zero"):
        chart.zoom(0.0)
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        chart.zoom(2.0, anchor_x=1.5)


def test_pointer_scroll_zoom_and_pointer_selection_use_retained_input_events() -> None:
    chart = LineChart(
        _series(),
        bounds=Rect(20.0, 30.0, 560.0, 280.0),
        key="pointer-line",
    )
    plot = chart.plot_bounds
    before = chart.viewport

    scroll_event = chart.emit(
        "pointer_scroll",
        event=_native(
            PlatformEventKind.POINTER_SCROLL,
            x=plot.x + plot.width * 0.75,
            y=plot.y + plot.height * 0.5,
            delta_y=-120.0,
        ),
    )

    assert scroll_event.default_prevented is True
    assert chart.viewport != before
    assert chart.zoom_level > 1.0

    position = chart.point_position(
        0,
        2,
        plot,
        chart.viewport.y_min,
        chart.viewport.y_max,
    )
    pointer_event = chart.emit(
        "pointer_down",
        event=_native(
            PlatformEventKind.POINTER_DOWN,
            x=position.x,
            y=position.y,
            button=PointerButton.LEFT,
        ),
    )

    assert pointer_event.default_prevented is True
    assert chart.selection is not None
    assert chart.selection.series_key == "downloads"
    assert chart.selection.point_index == 2


def test_keyboard_zoom_reset_and_selection_navigation() -> None:
    chart = LineChart(
        _series(),
        bounds=Rect(0.0, 0.0, 560.0, 280.0),
        key="keyboard-line",
    )

    plus = chart.emit(
        "key_down",
        event=_native(PlatformEventKind.KEY_DOWN, key_code=0xBB),
    )
    assert plus.default_prevented is True
    assert chart.zoom_level > 1.0

    right = chart.emit(
        "key_down",
        event=_native(PlatformEventKind.KEY_DOWN, key_code=0x27),
    )
    assert right.default_prevented is True
    assert chart.selection is not None
    assert chart.selection.point_index == 0

    chart.emit("key_down", event=_native(PlatformEventKind.KEY_DOWN, key_code=0x27))
    assert chart.selection is not None
    assert chart.selection.point_index == 1

    chart.emit("key_down", event=_native(PlatformEventKind.KEY_DOWN, key_code=0x28))
    assert chart.selection is not None
    assert chart.selection.series_index == 1

    chart.emit("key_down", event=_native(PlatformEventKind.KEY_DOWN, key_code=0x30))
    assert chart.zoom_level == 1.0

    chart.emit("key_down", event=_native(PlatformEventKind.KEY_DOWN, key_code=0x1B))
    assert chart.selection is None


def test_bar_chart_zoom_reflows_visible_category_slots_and_selection_marker() -> None:
    chart = BarChart(
        _series(),
        bounds=Rect(0.0, 0.0, 600.0, 300.0),
        key="interactive-bar",
    )

    full_slot = chart.plot_bounds.width / 5.0
    chart.zoom(2.0, anchor_x=0.5, anchor_y=0.5)
    chart.select(0, 2)
    scene = chart.build_scene_node()

    visible_bars = [
        node
        for node in scene.walk()
        if ":bar:" in node.key and node.key.startswith("interactive-bar:series:")
    ]
    assert visible_bars
    assert max(node.bounds.width for node in visible_bars) > full_slot * 0.1
    assert any(node.key == "interactive-bar:selection:marker" for node in scene.walk())


def test_set_series_clears_stale_selection_and_viewport() -> None:
    chart = LineChart(
        _series(),
        bounds=Rect(0.0, 0.0, 500.0, 260.0),
        key="replace-line",
    )
    chart.select(0, 3)
    chart.zoom(2.0)
    assert chart.selection is not None
    assert chart.zoom_level > 1.0

    chart.set_series((_series()[1],))

    assert chart.selection is None
    assert chart.zoom_level == 1.0
