import sys
import time

import pytest

from swirui import (
    App,
    ChartPoint,
    ChartSeries,
    Column,
    HeatmapCell,
    HeatmapChart,
    RadarChart,
    ScatterChart,
    ScatterPoint,
    ScatterSeries,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AdvancedCharts.{id(backend):x}"
    return backend


def _scatter() -> ScatterChart:
    return ScatterChart(
        (
            ScatterSeries(
                "native",
                "Native",
                (
                    ScatterPoint("a", "A", 1.0, 3.0),
                    ScatterPoint("b", "B", 2.0, 6.0),
                    ScatterPoint("c", "C", 4.0, 2.0),
                ),
            ),
        ),
        bounds=Rect(0.0, 0.0, 620.0, 170.0),
        key="native-scatter",
    )


def _heatmap() -> HeatmapChart:
    return HeatmapChart(
        (
            HeatmapCell("a", "A", "CPU", 0.2),
            HeatmapCell("b", "A", "GPU", 0.8),
            HeatmapCell("c", "B", "CPU", 0.5),
            HeatmapCell("d", "B", "GPU", 0.7),
        ),
        bounds=Rect(0.0, 0.0, 620.0, 170.0),
        key="native-heatmap",
    )


def _radar() -> RadarChart:
    return RadarChart(
        (
            ChartSeries(
                "native-radar",
                "Native radar",
                (
                    ChartPoint("cpu", "CPU", 8.0),
                    ChartPoint("gpu", "GPU", 6.0),
                    ChartPoint("ram", "RAM", 7.0),
                    ChartPoint("io", "I/O", 5.0),
                ),
            ),
        ),
        bounds=Rect(0.0, 0.0, 620.0, 190.0),
        key="native-radar",
        max_value=10.0,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Advanced chart smoke requires Windows")
def test_advanced_charts_render_through_one_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI advanced chart smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Advanced Charts", width=760, height=720))

    scatter = _scatter()
    heatmap = _heatmap()
    radar = _radar()
    root = Column(bounds=Rect(50.0, 40.0, 620.0, 570.0), spacing=10.0, key="chart-stack")
    root.add(scatter, heatmap, radar)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "native-scatter:series:0:point:2" in keys
        assert "native-heatmap:cell:3" in keys
        assert "native-radar:series:0:fill" in keys

        scatter.set_series(
            (
                ScatterSeries(
                    "updated",
                    "Updated",
                    (
                        ScatterPoint("a", "A", 2.0, 4.0),
                        ScatterPoint("b", "B", 3.0, 8.0),
                    ),
                ),
            )
        )
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
    finally:
        app.stop()
