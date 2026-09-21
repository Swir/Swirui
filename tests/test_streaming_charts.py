"""Deterministic acceptance coverage for live and streaming chart data."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from swirui import ChartPoint, StreamingChartSeries, StreamingLineChart
from swirui.rendering import Rect


def _point(index: int) -> ChartPoint:
    return ChartPoint(index, f"T{index}", float(index))


def test_streaming_series_is_bounded_and_reports_evictions() -> None:
    stream = StreamingChartSeries("cpu", "CPU", (_point(0), _point(1)), capacity=3)

    assert stream.append(_point(2)) is None
    dropped = stream.append(_point(3))

    assert dropped == _point(0)
    assert stream.point_count == 3
    assert stream.dropped_count == 1
    assert tuple(point.key for point in stream.snapshot().points) == (1, 2, 3)
    assert stream.latest == _point(3)


def test_streaming_snapshot_is_immutable_after_later_ingestion() -> None:
    stream = StreamingChartSeries("gpu", "GPU", (_point(0),), capacity=4)
    before = stream.snapshot()

    stream.append(_point(1))

    assert tuple(point.key for point in before.points) == (0,)
    assert tuple(point.key for point in stream.snapshot().points) == (0, 1)


def test_streaming_series_accepts_concurrent_producers_with_bounded_memory() -> None:
    stream = StreamingChartSeries("events", "Events", (_point(-1),), capacity=64)

    def produce(worker: int) -> None:
        stream.extend(
            tuple(
                ChartPoint((worker, index), f"{worker}:{index}", float(index))
                for index in range(100)
            )
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(produce, worker) for worker in range(4)]
        for future in futures:
            future.result()

    snapshot = stream.snapshot()
    assert stream.revision == 400
    assert stream.point_count == 64
    assert stream.dropped_count == 337
    assert len({point.key for point in snapshot.points}) == 64


def test_streaming_line_chart_refreshes_only_when_source_revision_changes() -> None:
    stream = StreamingChartSeries("cpu", "CPU", (_point(0),), capacity=4)
    chart = StreamingLineChart(
        (stream,),
        bounds=Rect(0.0, 0.0, 640.0, 280.0),
        key="live",
        title="Live CPU",
    )

    assert chart.refresh() is False
    stream.append(_point(1))
    assert chart.refresh() is True
    assert chart.refresh() is False

    keys = {node.key for node in chart.build_scene_node().walk()}
    assert "live:series:0:point:1" in keys
    snapshot = chart.accessibility_snapshot()
    assert snapshot.children[0].children[-1].name == "T1"


def test_streaming_line_chart_pause_buffers_data_until_resume() -> None:
    stream = StreamingChartSeries("load", "Load", (_point(0),), capacity=4)
    chart = StreamingLineChart(
        (stream,),
        bounds=Rect(0.0, 0.0, 640.0, 280.0),
        key="paused-live",
    )

    chart.pause()
    stream.extend((_point(1), _point(2)))
    assert chart.refresh() is False
    assert len(chart.series[0].points) == 1

    assert chart.resume() is True
    assert tuple(point.key for point in chart.series[0].points) == (0, 1, 2)


def test_streaming_line_chart_append_and_batch_refresh_retains_widget_identity() -> None:
    stream = StreamingChartSeries("load", "Load", (_point(0),), capacity=3)
    chart = StreamingLineChart(
        (stream,),
        bounds=Rect(0.0, 0.0, 640.0, 280.0),
        key="retained-live",
    )
    identity = id(chart)

    chart.append("load", _point(1))
    chart.extend("load", (_point(2), _point(3)), refresh=False)
    assert chart.refresh() is True

    assert id(chart) == identity
    assert tuple(point.key for point in chart.series[0].points) == (1, 2, 3)
    assert stream.dropped_count == 1


def test_streaming_series_rejects_invalid_capacity_and_duplicate_retained_keys() -> None:
    with pytest.raises(ValueError, match="capacity"):
        StreamingChartSeries("bad", "Bad", (_point(0),), capacity=1)

    duplicate = ChartPoint("same", "Same", 1.0)
    with pytest.raises(ValueError, match="Duplicate streaming chart point key"):
        StreamingChartSeries("bad", "Bad", (duplicate, duplicate))

    stream = StreamingChartSeries("dup", "Dup", (_point(0), _point(1)), capacity=4)
    with pytest.raises(ValueError, match="Duplicate streaming chart point key"):
        stream.append(_point(1))
