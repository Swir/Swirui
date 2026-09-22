"""Build a 100k-point retained line chart with bounded GPU scene fan-out."""

from __future__ import annotations

from swirui import App, ChartPoint, ChartSeries, LineChart, Window, mount
from swirui.rendering import Rect

POINTS = 100_000


def main() -> None:
    series = ChartSeries(
        "telemetry",
        "Telemetry",
        tuple(
            ChartPoint(index, f"P{index}", float(((index * 29) % 1_009) - 504))
            for index in range(POINTS)
        ),
    )
    app = App("SwirUI large dataset charts")
    window = app.add_window(Window(title="100k-point retained chart", width=1_280, height=720))
    chart = LineChart(
        (series,),
        bounds=Rect(40.0, 60.0, 1_180.0, 560.0),
        key="large-telemetry",
        title="100,000 source points / bounded retained projection",
        max_render_points=1_024,
        accessibility_point_limit=256,
    )
    mount(window, chart)
    app.run()


if __name__ == "__main__":
    main()
