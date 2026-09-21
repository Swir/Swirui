"""Launch a retained line/area/bar chart gallery."""

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
from swirui.rendering import Rect


def series(key: str, name: str, values: tuple[float, ...]) -> ChartSeries:
    labels = ("Mon", "Tue", "Wed", "Thu", "Fri")
    return ChartSeries(
        key,
        name,
        tuple(
            ChartPoint(f"{key}-{index}", label, value)
            for index, (label, value) in enumerate(zip(labels, values, strict=True))
        ),
    )


def main() -> None:
    downloads = series("downloads", "Downloads", (12.0, 19.0, 14.0, 27.0, 31.0))
    installs = series("installs", "Installs", (8.0, 13.0, 11.0, 20.0, 24.0))
    delta = series("delta", "Daily delta", (-3.0, 4.0, 7.0, -2.0, 5.0))

    line = LineChart(
        (downloads, installs),
        bounds=Rect(0.0, 0.0, 720.0, 210.0),
        title="Package activity",
        key="demo-line",
    )
    area = AreaChart(
        (delta,),
        bounds=Rect(0.0, 0.0, 720.0, 210.0),
        title="Daily delta",
        key="demo-area",
    )
    bars = BarChart(
        (downloads, installs),
        bounds=Rect(0.0, 0.0, 720.0, 210.0),
        title="Downloads vs installs",
        key="demo-bars",
    )

    root = Column(bounds=Rect(30.0, 24.0, 720.0, 650.0), spacing=10.0, key="gallery")
    root.add(line, area, bars)

    app = App("SwirUI Cartesian Charts")
    window = app.add_window(Window(title="SwirUI Charts", width=800, height=720))
    mount(window, root)
    app.start()
    app.run()


if __name__ == "__main__":
    main()
