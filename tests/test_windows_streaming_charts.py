"""Real Win32 + wgpu acceptance gate for live streaming charts."""

from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    App,
    ChartPoint,
    StreamingChartSeries,
    StreamingLineChart,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native gate")


def test_streaming_chart_refresh_reuses_one_persistent_wgpu_context() -> None:
    platform = Win32PlatformBackend()
    platform._class_name = f"SwirUI.StreamingCharts.{id(platform):x}"
    renderer = WgpuRenderer()
    app = App(
        "streaming charts native gate",
        platform_backend=platform,
        renderer=renderer,
    )
    window = app.add_window(Window(title="Streaming charts", width=900, height=520))

    stream = StreamingChartSeries(
        "telemetry",
        "Telemetry",
        tuple(ChartPoint(index, str(index), float(index % 9)) for index in range(24)),
        capacity=48,
    )
    chart = StreamingLineChart(
        (stream,),
        bounds=Rect(60.0, 40.0, 760.0, 400.0),
        key="native-stream",
        title="Live telemetry",
    )
    runtime = mount(window, chart)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        stream.extend(
            tuple(
                ChartPoint(24 + index, str(24 + index), float((index * 3) % 17))
                for index in range(80)
            )
        )
        assert chart.refresh() is True
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1

        assert stream.point_count == 48
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.last_rectangle_count > 0
        assert renderer.last_text_count > 0
        assert renderer.last_path_count > 0
        assert runtime.generation > 1
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "native-stream:series:0:point:47" in keys
    finally:
        app.stop()
