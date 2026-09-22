"""Launch a representative chart gallery on the explicit Rust + wgpu renderer."""

from __future__ import annotations

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


def main() -> int:
    renderer = WgpuRenderer()
    app = App("SwirUI GPU Charts", renderer=renderer)
    window = app.add_window(Window(title="SwirUI — Native GPU Charts", width=900, height=820))

    line = LineChart(
        (_series("activity", (12.0, 19.0, 14.0, 27.0, 31.0)),),
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        title="Cartesian retained paths",
    )
    pie = PieChart(
        _series("share", (31.0, 24.0, 18.0, 27.0)),
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        title="Radial retained paths",
    )
    gauge = GaugeChart(
        68.0,
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        title="Specialized retained paths",
    )
    stream = StreamingChartSeries(
        "live",
        "Live",
        tuple(ChartPoint(index, f"T{index}", float((index * 3) % 11)) for index in range(16)),
        capacity=32,
    )
    live = StreamingLineChart(
        (stream,),
        bounds=Rect(0.0, 0.0, 720.0, 155.0),
        title="Bounded streaming paths",
    )

    root = Column(bounds=Rect(70.0, 45.0, 720.0, 650.0), spacing=10.0)
    root.add(line, pie, gauge, live)
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
