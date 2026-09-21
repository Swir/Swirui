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
from swirui.rendering import Rect

app = App("SwirUI advanced charts")
window = app.add_window(Window(title="Scatter / Heatmap / Radar", width=920, height=820))

scatter = ScatterChart(
    (
        ScatterSeries(
            "builds",
            "Builds",
            (
                ScatterPoint("a", "A", 1.0, 4.0),
                ScatterPoint("b", "B", 2.0, 7.0),
                ScatterPoint("c", "C", 4.0, 5.0),
            ),
        ),
    ),
    bounds=Rect(0.0, 0.0, 760.0, 210.0),
    title="Build duration vs throughput",
)

heatmap = HeatmapChart(
    (
        HeatmapCell("mon-cpu", "Mon", "CPU", 0.45),
        HeatmapCell("mon-gpu", "Mon", "GPU", 0.82),
        HeatmapCell("tue-cpu", "Tue", "CPU", 0.61),
        HeatmapCell("tue-gpu", "Tue", "GPU", 0.70),
    ),
    bounds=Rect(0.0, 0.0, 760.0, 210.0),
    title="Resource load",
)

radar = RadarChart(
    (
        ChartSeries(
            "engine",
            "Engine",
            (
                ChartPoint("cpu", "CPU", 8.0),
                ChartPoint("gpu", "GPU", 9.0),
                ChartPoint("memory", "Memory", 7.0),
                ChartPoint("io", "I/O", 6.0),
                ChartPoint("startup", "Startup", 8.0),
            ),
        ),
    ),
    bounds=Rect(0.0, 0.0, 760.0, 250.0),
    title="Engine profile",
    max_value=10.0,
)

root = Column(bounds=Rect(70.0, 40.0, 760.0, 710.0), spacing=12.0)
root.add(scatter, heatmap, radar)
mount(window, root)

if __name__ == "__main__":
    app.run()
