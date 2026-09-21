"""Micro-benchmark bounded streaming ingestion and retained refresh."""

from __future__ import annotations

import statistics
import time

from swirui import ChartPoint, StreamingChartSeries, StreamingLineChart
from swirui.rendering import Rect

POINTS = 20_000
REFRESH_ITERATIONS = 80


def main() -> None:
    stream = StreamingChartSeries(
        "telemetry",
        "Telemetry",
        (ChartPoint(-1, "seed", 0.0),),
        capacity=256,
    )
    chart = StreamingLineChart(
        (stream,),
        bounds=Rect(0.0, 0.0, 1200.0, 480.0),
        key="benchmark-stream",
    )

    started = time.perf_counter()
    for index in range(POINTS):
        stream.append(ChartPoint(index, str(index), float(index % 101)))
    ingestion_ms = (time.perf_counter() - started) * 1000.0

    samples: list[float] = []
    for index in range(REFRESH_ITERATIONS):
        stream.append(ChartPoint(POINTS + index, str(POINTS + index), float(index % 101)))
        started = time.perf_counter()
        chart.refresh()
        chart.build_scene_node()
        samples.append((time.perf_counter() - started) * 1000.0)

    print(
        "streaming_charts "
        f"ingest{POINTS}={ingestion_ms:.3f}ms "
        f"capacity={stream.capacity} "
        f"refresh+scene median={statistics.median(samples):.3f}ms "
        f"max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
