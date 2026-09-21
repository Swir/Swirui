"""Run a bounded live telemetry stream through a retained SwirUI line chart."""

from __future__ import annotations

import math
import time

from swirui import (
    App,
    AppConfig,
    ChartPoint,
    StreamingChartSeries,
    StreamingLineChart,
    Window,
    mount,
)
from swirui.core import Event
from swirui.rendering import Rect

START = time.monotonic()
INDEX = 0

stream = StreamingChartSeries(
    "gpu",
    "GPU frame load",
    (ChartPoint(0, "0.0s", 50.0),),
    capacity=120,
)
chart = StreamingLineChart(
    (stream,),
    bounds=Rect(40.0, 40.0, 920.0, 500.0),
    key="live-demo",
    title="Live GPU-style telemetry — bounded to 120 samples",
    y_min=0.0,
    y_max=100.0,
)

app = App("SwirUI Streaming Charts", config=AppConfig(target_fps=60))
window = app.add_window(Window(title="SwirUI — Live Streaming Chart", width=1000, height=580))
mount(window, chart)


def publish_sample(_: Event) -> None:
    global INDEX
    INDEX += 1
    elapsed = time.monotonic() - START
    value = 52.0 + math.sin(elapsed * 2.1) * 26.0 + math.sin(elapsed * 7.0) * 7.0
    stream.append(ChartPoint(INDEX, f"{elapsed:.1f}s", value))
    if chart.refresh():
        app.invalidate(window)


app.on("frame_rendered", publish_sample)

if __name__ == "__main__":
    raise SystemExit(app.run())
