"""Micro-benchmark interactive cartesian zoom, selection and retained compilation."""

from __future__ import annotations

import statistics
import time

from swirui import ChartPoint, ChartSeries, LineChart
from swirui.rendering import Rect

POINTS = 2_000
ITERATIONS = 120


def main() -> None:
    series = ChartSeries(
        "signal",
        "Signal",
        tuple(
            ChartPoint(index, str(index), float((index * 17) % 101))
            for index in range(POINTS)
        ),
    )
    chart = LineChart(
        (series,),
        bounds=Rect(0.0, 0.0, 1280.0, 520.0),
        key="interactive-benchmark",
    )

    chart.zoom(4.0)
    samples: list[float] = []
    for iteration in range(ITERATIONS):
        index = (iteration * 13) % POINTS
        started = time.perf_counter()
        chart.select(0, index)
        chart.zoom(1.01 if iteration % 2 == 0 else 1.0 / 1.01)
        chart.build_scene_node()
        samples.append((time.perf_counter() - started) * 1000.0)

    print(
        "interactive_charts "
        f"points={POINTS} iterations={ITERATIONS} "
        f"interaction+scene median={statistics.median(samples):.3f}ms "
        f"p95={statistics.quantiles(samples, n=20)[18]:.3f}ms "
        f"max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
