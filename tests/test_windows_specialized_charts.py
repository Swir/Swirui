"""Real Win32 + wgpu acceptance gate for specialized charts."""

from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    App,
    CandlestickChart,
    CandlestickPoint,
    Column,
    GaugeChart,
    TimelineChart,
    TimelineChartItem,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native gate")


def test_specialized_charts_render_through_one_persistent_wgpu_context() -> None:
    platform = Win32PlatformBackend()
    platform._class_name = f"SwirUI.SpecializedCharts.{id(platform):x}"
    renderer = WgpuRenderer()
    app = App(
        "specialized charts native gate",
        platform_backend=platform,
        renderer=renderer,
    )
    window = app.add_window(Window(title="Specialized charts", width=900, height=760))

    gauge = GaugeChart(
        72.0,
        bounds=Rect(0.0, 0.0, 760.0, 210.0),
        key="native-gauge",
        title="GPU load",
    )
    candles = CandlestickChart(
        (
            CandlestickPoint("a", "09:00", 100.0, 108.0, 96.0, 105.0),
            CandlestickPoint("b", "10:00", 105.0, 111.0, 101.0, 103.0),
            CandlestickPoint("c", "11:00", 103.0, 116.0, 102.0, 114.0),
        ),
        bounds=Rect(0.0, 0.0, 760.0, 220.0),
        key="native-candles",
        title="OHLC",
    )
    timeline = TimelineChart(
        (
            TimelineChartItem("prepare", "Prepare", 0.0, 2.0),
            TimelineChartItem("render", "Render", 1.5, 5.0),
            TimelineChartItem("present", "Present", 4.8, 6.0),
        ),
        bounds=Rect(0.0, 0.0, 760.0, 220.0),
        key="native-timeline",
        title="Frame pipeline",
    )
    root = Column(bounds=Rect(60.0, 28.0, 760.0, 690.0), spacing=10.0)
    root.add(gauge, candles, timeline)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "native-gauge:segment:0" in keys
        assert "native-candles:candle:2:body" in keys
        assert "native-timeline:item:2:bar" in keys

        gauge.value = 84.0
        candles.set_points(
            (
                CandlestickPoint("a", "09:00", 100.0, 109.0, 96.0, 108.0),
                CandlestickPoint("b", "10:00", 108.0, 114.0, 102.0, 104.0),
                CandlestickPoint("c", "11:00", 104.0, 119.0, 103.0, 117.0),
            )
        )
        timeline.set_items(
            (
                TimelineChartItem("prepare", "Prepare", 0.0, 1.8),
                TimelineChartItem("render", "Render", 1.4, 5.2),
                TimelineChartItem("present", "Present", 4.9, 6.4),
            )
        )
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1

        assert renderer.persistent_context_count == initial_contexts
        assert renderer.last_rectangle_count > 0
        assert renderer.last_text_count > 0
        assert renderer.last_path_count > 0
        assert runtime.generation > 1
    finally:
        app.stop()
