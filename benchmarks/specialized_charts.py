"""Micro-benchmark retained specialized chart scene construction."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

from swirui import CandlestickChart, CandlestickPoint, TimelineChart, TimelineChartItem
from swirui.rendering import Rect

ITERATIONS = 50


def _measure(callback: Callable[[], object]) -> tuple[float, float]:
    samples: list[float] = []
    for _ in range(ITERATIONS):
        started = time.perf_counter()
        callback()
        samples.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(samples), max(samples)


def main() -> None:
    candles = tuple(
        CandlestickPoint(
            index,
            str(index),
            open_value := 100.0 + index % 17,
            max(open_value, close_value := open_value + ((index % 9) - 4.0)) + 6.0,
            min(open_value, close_value) - 6.0,
            close_value,
        )
        for index in range(500)
    )
    candlestick = CandlestickChart(
        candles,
        bounds=Rect(0.0, 0.0, 1200.0, 480.0),
        key="benchmark-candles",
    )
    timeline = TimelineChart(
        tuple(
            TimelineChartItem(index, f"Task {index}", float(index), float(index + 5))
            for index in range(100)
        ),
        bounds=Rect(0.0, 0.0, 1200.0, 640.0),
        key="benchmark-timeline",
    )

    candle_median, candle_max = _measure(candlestick.build_scene_node)
    timeline_median, timeline_max = _measure(timeline.build_scene_node)
    print(
        "specialized_charts "
        f"candles500 median={candle_median:.3f}ms max={candle_max:.3f}ms "
        f"timeline100 median={timeline_median:.3f}ms max={timeline_max:.3f}ms"
    )


if __name__ == "__main__":
    main()
