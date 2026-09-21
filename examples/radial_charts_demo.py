"""Launch a retained pie/donut chart gallery."""

from swirui import App, ChartPoint, ChartSeries, Column, DonutChart, PieChart, Window, mount
from swirui.rendering import Rect


def traffic_series() -> ChartSeries:
    return ChartSeries(
        "traffic",
        "Traffic sources",
        (
            ChartPoint("docs", "Docs", 34.0),
            ChartPoint("search", "Search", 28.0),
            ChartPoint("direct", "Direct", 22.0),
            ChartPoint("social", "Social", 16.0),
        ),
    )


def main() -> None:
    data = traffic_series()
    pie = PieChart(
        data,
        bounds=Rect(0.0, 0.0, 720.0, 280.0),
        title="Traffic split",
        key="demo-pie",
    )
    donut = DonutChart(
        data,
        bounds=Rect(0.0, 0.0, 720.0, 280.0),
        title="Traffic share",
        key="demo-donut",
        inner_radius_ratio=0.58,
    )

    root = Column(bounds=Rect(30.0, 24.0, 720.0, 590.0), spacing=14.0, key="radial-gallery")
    root.add(pie, donut)

    app = App("SwirUI Radial Charts")
    window = app.add_window(Window(title="SwirUI Pie & Donut Charts", width=800, height=660))
    mount(window, root)
    app.start()
    app.run()


if __name__ == "__main__":
    main()
