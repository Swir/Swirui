"""Deterministic acceptance coverage for gauge, candlestick and timeline charts."""

from __future__ import annotations

import pytest

from swirui import (
    CandlestickChart,
    CandlestickPoint,
    GaugeChart,
    TimelineChart,
    TimelineChartItem,
)
from swirui.rendering import Color, Rect


def _candles(count: int = 4) -> tuple[CandlestickPoint, ...]:
    return tuple(
        CandlestickPoint(
            index,
            f"D{index + 1}",
            100.0 + index,
            106.0 + index,
            96.0 + index,
            103.0 + index if index % 2 == 0 else 98.0 + index,
        )
        for index in range(count)
    )


def test_gauge_clamps_value_and_exposes_accessible_progress() -> None:
    gauge = GaugeChart(
        135.0,
        minimum=0.0,
        maximum=120.0,
        bounds=Rect(0.0, 0.0, 320.0, 240.0),
        key="gauge",
        title="Thermal headroom",
        segments=24,
    )

    assert gauge.value == 120.0
    assert gauge.progress == 1.0
    keys = {node.key for node in gauge.build_scene_node().walk()}
    assert "gauge:segment:0" in keys
    assert "gauge:segment:23" in keys
    assert "gauge:value" in keys

    snapshot = gauge.accessibility_snapshot()
    assert snapshot.value == 120.0
    assert snapshot.min_value == 0.0
    assert snapshot.max_value == 120.0
    assert snapshot.value_text == "120"

    gauge.value = -10.0
    assert gauge.value == 0.0


def test_candlestick_validates_ohlc_and_builds_wick_body_pairs() -> None:
    chart = CandlestickChart(
        _candles(),
        bounds=Rect(0.0, 0.0, 640.0, 280.0),
        key="candles",
        title="OHLC",
    )

    assert chart.y_domain == (96.0, 109.0)
    keys = {node.key for node in chart.build_scene_node().walk()}
    for index in range(4):
        assert f"candles:candle:{index}:wick" in keys
        assert f"candles:candle:{index}:body" in keys

    snapshot = chart.accessibility_snapshot()
    assert len(snapshot.children) == 4
    assert "open 100" in snapshot.children[0].value_text
    assert "close 103" in snapshot.children[0].value_text

    with pytest.raises(ValueError, match="contain open and close"):
        CandlestickPoint("bad", "bad", 10.0, 9.0, 8.0, 10.0)


def test_candlestick_updates_retained_dataset_without_replacing_widget() -> None:
    chart = CandlestickChart(
        _candles(2),
        bounds=Rect(0.0, 0.0, 500.0, 240.0),
        key="candles",
    )
    updated = _candles(6)

    chart.set_points(updated)

    assert chart.points == updated
    keys = {node.key for node in chart.build_scene_node().walk()}
    assert "candles:candle:5:body" in keys


def test_timeline_chart_maps_intervals_to_lanes_and_accessibility() -> None:
    items = (
        TimelineChartItem("compile", "Compile", 0.0, 3.0, Color.from_hex("#38BDF8")),
        TimelineChartItem("test", "Test", 2.0, 7.0),
        TimelineChartItem("package", "Package", 6.0, 9.0),
    )
    chart = TimelineChart(
        items,
        bounds=Rect(0.0, 0.0, 680.0, 300.0),
        key="timeline-chart",
        title="Build pipeline",
    )

    assert chart.domain == (0.0, 9.0)
    keys = {node.key for node in chart.build_scene_node().walk()}
    assert "timeline-chart:item:0:bar" in keys
    assert "timeline-chart:item:2:bar" in keys
    assert "timeline-chart:tick:4" in keys

    snapshot = chart.accessibility_snapshot()
    assert snapshot.value_text == "3 intervals"
    assert snapshot.children[1].name == "Test"
    assert snapshot.children[1].value_text == "2 to 7"


def test_specialized_charts_reject_duplicate_stable_keys() -> None:
    candle = CandlestickPoint("same", "A", 10.0, 12.0, 8.0, 11.0)
    with pytest.raises(ValueError, match="Duplicate candlestick key"):
        CandlestickChart(
            (candle, candle),
            bounds=Rect(0.0, 0.0, 500.0, 240.0),
        )

    item = TimelineChartItem("same", "Task", 0.0, 1.0)
    with pytest.raises(ValueError, match="Duplicate timeline item key"):
        TimelineChart(
            (item, item),
            bounds=Rect(0.0, 0.0, 500.0, 240.0),
        )


def test_candlestick_scene_scales_linearly_for_dense_acceptance_fixture() -> None:
    candles = tuple(
        CandlestickPoint(
            index,
            str(index),
            open_value := 100.0 + (index % 11),
            max(open_value, close_value := open_value + ((index % 9) - 4.0)) + 6.0,
            min(open_value, close_value) - 6.0,
            close_value,
        )
        for index in range(500)
    )
    chart = CandlestickChart(
        candles,
        bounds=Rect(0.0, 0.0, 1200.0, 480.0),
        key="dense-candles",
    )

    nodes = tuple(chart.build_scene_node().walk())

    # One wick + one body per candle, plus bounded axes/labels/background.
    assert 1000 < len(nodes) < 1100
