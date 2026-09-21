"""Launch the retained gauge, candlestick and timeline chart gallery."""

from swirui import (
    App,
    CandlestickChart,
    CandlestickPoint,
    Column,
    GaugeChart,
    TimelineChart,
    TimelineChartItem,
    Window,
    mount,
)
from swirui.rendering import Rect


def main() -> int:
    gauge = GaugeChart(
        72.0,
        bounds=Rect(0.0, 0.0, 760.0, 210.0),
        title="GPU headroom",
        key="demo-gauge",
    )
    candles = CandlestickChart(
        (
            CandlestickPoint("mon", "Mon", 101.0, 110.0, 97.0, 108.0),
            CandlestickPoint("tue", "Tue", 108.0, 113.0, 103.0, 105.0),
            CandlestickPoint("wed", "Wed", 105.0, 118.0, 104.0, 116.0),
            CandlestickPoint("thu", "Thu", 116.0, 121.0, 109.0, 111.0),
            CandlestickPoint("fri", "Fri", 111.0, 125.0, 110.0, 123.0),
        ),
        bounds=Rect(0.0, 0.0, 760.0, 220.0),
        title="OHLC activity",
        key="demo-candles",
    )
    timeline = TimelineChart(
        (
            TimelineChartItem("input", "Input", 0.0, 1.1),
            TimelineChartItem("layout", "Layout", 0.8, 2.6),
            TimelineChartItem("render", "Render", 2.2, 5.4),
            TimelineChartItem("present", "Present", 5.0, 6.0),
        ),
        bounds=Rect(0.0, 0.0, 760.0, 220.0),
        title="Frame pipeline",
        key="demo-timeline",
    )

    root = Column(bounds=Rect(70.0, 30.0, 760.0, 690.0), spacing=10.0)
    root.add(gauge, candles, timeline)

    app = App("SwirUI specialized charts")
    window = app.add_window(Window(title="Gauge / Candlestick / Timeline", width=900, height=760))
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
