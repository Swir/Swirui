import sys
import time

import pytest

from swirui import App, ChartPoint, ChartSeries, Column, DonutChart, PieChart, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _series(key: str, values: tuple[float, ...]) -> ChartSeries:
    return ChartSeries(
        key,
        key.title(),
        tuple(
            ChartPoint(f"{key}-{index}", f"Slice {index + 1}", value)
            for index, value in enumerate(values)
        ),
    )


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.RadialCharts.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Radial chart smoke requires Windows")
def test_radial_charts_render_through_one_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI radial chart smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Radial Charts", width=760, height=560))

    pie = PieChart(
        _series("pie", (4.0, 7.0, 5.0, 2.0)),
        bounds=Rect(0.0, 0.0, 620.0, 220.0),
        key="native-pie",
        title="Pie",
    )
    donut = DonutChart(
        _series("donut", (6.0, 3.0, 8.0)),
        bounds=Rect(0.0, 0.0, 620.0, 220.0),
        key="native-donut",
        title="Donut",
    )
    root = Column(bounds=Rect(60.0, 40.0, 620.0, 460.0), spacing=12.0, key="radial-stack")
    root.add(pie, donut)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "native-pie:slice:0:segment:0" in keys
        assert "native-donut:slice:2:segment:0" in keys

        pie.set_series(_series("pie-refresh", (2.0, 9.0, 4.0, 7.0)))
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
    finally:
        app.stop()
