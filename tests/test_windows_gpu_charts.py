"""Cross-family Win32 + wgpu acceptance gate for SwirUI charts."""

from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    App,
    ChartPoint,
    ChartSeries,
    Column,
    GaugeChart,
    LineChart,
    PieChart,
    StreamingChartSeries,
    StreamingLineChart,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native GPU gate")


def _series(key: str, values: tuple[float, ...]) -> ChartSeries:
    return ChartSeries(
        key,
        key.title(),
        tuple(
            ChartPoint(f"{key}-{index}", f"P{index + 1}", value)
            for index, value in enumerate(values)
        ),
    )


def test_chart_families_share_one_persistent_native_gpu_context() -> None:
    platform = Win32PlatformBackend()
    platform._class_name = f"SwirUI.GpuCharts.{id(platform):x}"
    renderer = WgpuRenderer()
    app = App("gpu chart native gate", platform_backend=platform, renderer=renderer)
    window = app.add_window(Window(title="GPU charts", width=900, height=820))

    line = LineChart(
        (_series("line", (4.0, 9.0, 6.0, 12.0)),),
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        key="gpu-line",
        title="Cartesian path submission",
    )
    pie = PieChart(
        _series("pie", (18.0, 27.0, 34.0, 21.0)),
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        key="gpu-pie",
        title="Radial path submission",
    )
    gauge = GaugeChart(
        42.0,
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        key="gpu-gauge",
        title="Specialized path submission",
    )
    stream = StreamingChartSeries(
        "telemetry",
        "Telemetry",
        tuple(ChartPoint(index, f"T{index}", float(index % 7)) for index in range(12)),
        capacity=24,
    )
    live = StreamingLineChart(
        (stream,),
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        key="gpu-stream",
        title="Streaming retained submission",
    )

    root = Column(bounds=Rect(70.0, 45.0, 720.0, 650.0), spacing=10.0, key="gpu-chart-stack")
    root.add(line, pie, gauge, live)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
        assert renderer.last_rectangle_count > 0
        assert renderer.last_text_count > 0
        assert renderer.last_path_count > 0

        initial_contexts = renderer.persistent_context_count
        initial_generation = runtime.generation
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "gpu-line:series:0:line:0" in keys
        assert any(key.startswith("gpu-pie:slice:0:segment:") for key in keys)
        assert "gpu-gauge:segment:0" in keys
        assert "gpu-stream:series:0:line:0" in keys

        gauge.value = 73.0
        stream.append(ChartPoint(12, "T12", 11.0))
        assert live.refresh() is True
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1

        assert renderer.persistent_context_count == initial_contexts
        assert renderer.last_rectangle_count > 0
        assert renderer.last_text_count > 0
        assert renderer.last_path_count > 0
        assert runtime.generation > initial_generation
    finally:
        app.stop()
