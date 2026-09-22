import sys
import time

import pytest

from swirui import App, ChartPoint, ChartSeries, LineChart, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer

POINTS = 50_000
RENDER_BUDGET = 384


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.LargeDatasetCharts.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Large dataset chart smoke requires Windows")
def test_large_dataset_chart_keeps_native_gpu_context_and_scene_bounded() -> None:
    series = ChartSeries(
        "telemetry",
        "Telemetry",
        tuple(
            ChartPoint(index, f"P{index}", float(((index * 31) % 1_013) - 506))
            for index in range(POINTS)
        ),
    )
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI large dataset charts", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="Large Dataset Chart", width=1_100, height=620))
    chart = LineChart(
        (series,),
        bounds=Rect(40.0, 40.0, 1_000.0, 500.0),
        key="native-large-chart",
        max_render_points=RENDER_BUDGET,
        accessibility_point_limit=96,
    )
    mount(window, chart)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert window.scene is not None
        initial_nodes = sum(1 for _node in window.scene.walk())
        assert initial_nodes <= RENDER_BUDGET * 2 + 64

        chart.zoom(8.0)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == 1
        assert window.scene is not None
        zoomed_nodes = sum(1 for _node in window.scene.walk())
        assert zoomed_nodes <= RENDER_BUDGET * 2 + 64
    finally:
        app.stop()
