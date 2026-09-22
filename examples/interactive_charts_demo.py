"""Launch a retained cartesian chart with wheel zoom and point selection."""

from swirui import App, ChartPoint, ChartSeries, LineChart, Window, mount
from swirui.rendering import Rect


def main() -> None:
    values = (12.0, 19.0, 14.0, 27.0, 31.0, 26.0, 36.0, 29.0, 42.0, 38.0)
    chart = LineChart(
        (
            ChartSeries(
                "downloads",
                "Downloads",
                tuple(
                    ChartPoint(index, f"P{index + 1}", value)
                    for index, value in enumerate(values)
                ),
            ),
        ),
        bounds=Rect(36.0, 42.0, 760.0, 360.0),
        key="interactive-demo",
        title="Interactive package activity",
    )

    chart.on(
        "selection_changed",
        lambda event: print("selection:", event.data.get("selection")),
    )
    chart.on(
        "zoom_changed",
        lambda event: print("viewport:", event.data.get("viewport")),
    )

    app = App("SwirUI Interactive Charts")
    window = app.add_window(
        Window(title="Wheel zoom · click select · +/- zoom · 0 reset", width=840, height=460)
    )
    mount(window, chart)
    app.start()
    app.run()


if __name__ == "__main__":
    main()
