import sys
import time

import pytest

from swirui import App, ChartPoint, ChartSeries, LineChart, Window, mount
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.InteractiveCharts.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Interactive chart smoke requires Windows")
def test_interactive_chart_routes_native_scroll_selection_and_gpu_rebuild() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI interactive charts", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="Interactive Chart", width=720, height=420))
    chart = LineChart(
        (
            ChartSeries(
                "telemetry",
                "Telemetry",
                tuple(
                    ChartPoint(index, f"P{index + 1}", value)
                    for index, value in enumerate((2.0, 8.0, 4.0, 11.0, 6.0))
                ),
            ),
        ),
        bounds=Rect(40.0, 40.0, 620.0, 300.0),
        key="native-interactive-chart",
        title="Telemetry",
    )
    runtime = mount(window, chart)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1

        plot = chart.plot_bounds
        window._apply_platform_event(
            PlatformEvent(
                PlatformEventKind.POINTER_SCROLL,
                window.native_handle,
                x=(plot.x + plot.width * 0.5) * window.scale,
                y=(plot.y + plot.height * 0.5) * window.scale,
                delta_y=-120.0,
            )
        )
        assert chart.zoom_level > 1.0

        position = chart.point_position(
            0,
            2,
            chart.plot_bounds,
            chart.viewport.y_min,
            chart.viewport.y_max,
        )
        window._apply_platform_event(
            PlatformEvent(
                PlatformEventKind.POINTER_DOWN,
                window.native_handle,
                x=position.x * window.scale,
                y=position.y * window.scale,
                button=PointerButton.LEFT,
            )
        )
        assert chart.selection is not None
        assert chart.selection.point_index == 2
        assert window.focused_component is chart

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == 1
        assert runtime.generation >= 3
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert "native-interactive-chart:selection:marker" in keys
    finally:
        app.stop()
