import sys
import time

import pytest

from swirui import (
    App,
    AreaChart,
    BarChart,
    ChartPoint,
    ChartSeries,
    Column,
    LineChart,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _series(key: str, values: tuple[float, ...]) -> ChartSeries:
    return ChartSeries(
        key,
        key.title(),
        tuple(
            ChartPoint(f"{key}-{index}", f"P{index + 1}", value)
            for index, value in enumerate(values)
        ),
    )


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.CartesianCharts.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Cartesian chart smoke requires Windows")
def test_cartesian_charts_render_through_one_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI chart smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Charts", width=760, height=680))

    line = LineChart(
        (_series("line", (4.0, 9.0, 6.0)),),
        bounds=Rect(0.0, 0.0, 620.0, 170.0),
        key="native-line",
    )
    area = AreaChart(
        (_series("area", (-3.0, 5.0, 2.0)),),
        bounds=Rect(0.0, 0.0, 620.0, 170.0),
        key="native-area",
    )
    bar = BarChart(
        (_series("bar", (3.0, 7.0, 5.0)),),
        bounds=Rect(0.0, 0.0, 620.0, 170.0),
        key="native-bar",
    )
    root = Column(bounds=Rect(50.0, 40.0, 620.0, 550.0), spacing=10.0, key="chart-stack")
    root.add(line, area, bar)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "native-line:series:0:line:0" in keys
        assert "native-area:series:0:area:0:a" in keys
        assert "native-bar:series:0:bar:1" in keys

        line.set_series((_series("line-refresh", (8.0, 2.0, 10.0)),))
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
    finally:
        app.stop()
