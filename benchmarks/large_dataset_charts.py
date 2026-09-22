"""Measure bounded retained-scene construction for a 100k-point line chart."""

from __future__ import annotations

import statistics
import time

from swirui import ChartPoint, ChartSeries, LineChart
from swirui.rendering import Rect

POINTS = 100_000
ITERATIONS = 12
RENDER_BUDGET = 768


def main() -> None:
    series = ChartSeries(
        "signal",
        "Signal",
        tuple(
            ChartPoint(index, str(index), float(((index * 41) % 2_003) - 1_001))
            for index in range(POINTS)
        ),
    )
    chart = LineChart(
        (series,),
        bounds=Rect(0.0, 0.0, 1_280.0, 520.0),
        key="large-dataset-benchmark",
        max_render_points=RENDER_BUDGET,
        accessibility_point_limit=128,
    )

    samples: list[float] = []
    node_counts: list[int] = []
    for iteration in range(ITERATIONS):
        if iteration:
            chart.zoom(1.015 if iteration % 2 else 1.0 / 1.015)
        started = time.perf_counter()
        scene = chart.build_scene_node()
        samples.append((time.perf_counter() - started) * 1_000.0)
        node_counts.append(sum(1 for _node in scene.walk()))

    max_nodes = max(node_counts)
    if max_nodes > RENDER_BUDGET * 2 + 64:
        raise RuntimeError(f"retained scene fan-out escaped budget: {max_nodes} nodes")
    print(
        "large_dataset_charts "
        f"source_points={POINTS} render_budget={RENDER_BUDGET} max_nodes={max_nodes} "
        f"build median={statistics.median(samples):.3f}ms "
        f"p95={statistics.quantiles(samples, n=20)[18]:.3f}ms "
        f"max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
