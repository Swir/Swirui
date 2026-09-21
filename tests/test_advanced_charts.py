from __future__ import annotations

import math

import pytest

from swirui import (
    ChartPoint,
    ChartSeries,
    HeatmapCell,
    HeatmapChart,
    RadarChart,
    ScatterChart,
    ScatterPoint,
    ScatterSeries,
)
from swirui.core import AccessibilityRole
from swirui.rendering import Rect, SceneNodeKind


def _scatter_series() -> tuple[ScatterSeries, ...]:
    return (
        ScatterSeries(
            "latency",
            "Latency",
            (
                ScatterPoint("a", "A", 1.0, 7.0),
                ScatterPoint("b", "B", 2.5, 4.0),
                ScatterPoint("c", "C", 5.0, 9.0),
            ),
        ),
        ScatterSeries(
            "throughput",
            "Throughput",
            (
                ScatterPoint("a", "A", 1.5, 3.0),
                ScatterPoint("b", "B", 3.0, 6.0),
            ),
        ),
    )


def _radar_series() -> tuple[ChartSeries, ...]:
    return (
        ChartSeries(
            "stable",
            "Stable",
            (
                ChartPoint("cpu", "CPU", 8.0),
                ChartPoint("gpu", "GPU", 6.0),
                ChartPoint("memory", "Memory", 7.0),
                ChartPoint("io", "I/O", 5.0),
            ),
        ),
        ChartSeries(
            "preview",
            "Preview",
            (
                ChartPoint("cpu", "CPU", 6.0),
                ChartPoint("gpu", "GPU", 9.0),
                ChartPoint("memory", "Memory", 5.0),
                ChartPoint("io", "I/O", 8.0),
            ),
        ),
    )


def test_scatter_chart_builds_numeric_axes_markers_and_accessibility() -> None:
    chart = ScatterChart(
        _scatter_series(),
        bounds=Rect(10.0, 20.0, 520.0, 280.0),
        key="scatter",
        title="Runtime profile",
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}

    assert chart.x_domain == (1.0, 5.0)
    assert chart.y_domain == (3.0, 9.0)
    assert "scatter:axis:x" in keys
    assert "scatter:grid:x:4" in keys
    assert "scatter:series:0:point:2" in keys
    assert "scatter:series:1:point:1" in keys

    snapshot = chart.accessibility_snapshot()
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.value_text == "2 series"
    assert snapshot.children[0].children[1].name == "B"
    assert snapshot.children[0].children[1].value_text == "2.5, 4"


def test_scatter_chart_supports_explicit_domains_and_replacement() -> None:
    chart = ScatterChart(
        _scatter_series(),
        bounds=Rect(0.0, 0.0, 400.0, 220.0),
        x_min=0.0,
        x_max=10.0,
        y_min=-2.0,
        y_max=12.0,
    )

    assert chart.x_domain == (0.0, 10.0)
    assert chart.y_domain == (-2.0, 12.0)

    chart.set_series((_scatter_series()[1],))
    assert [series.key for series in chart.series] == ["throughput"]


def test_heatmap_chart_builds_sparse_matrix_labels_values_and_accessibility() -> None:
    chart = HeatmapChart(
        (
            HeatmapCell("mon-cpu", "Mon", "CPU", 0.25),
            HeatmapCell("mon-gpu", "Mon", "GPU", 0.75),
            HeatmapCell("tue-cpu", "Tue", "CPU", 0.50),
        ),
        bounds=Rect(0.0, 0.0, 420.0, 240.0),
        key="heatmap",
        title="Load",
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}

    assert chart.rows == ("Mon", "Tue")
    assert chart.columns == ("CPU", "GPU")
    assert chart.value_domain == (0.25, 0.75)
    assert "heatmap:row:1" in keys
    assert "heatmap:column:1" in keys
    assert "heatmap:cell:2" in keys
    assert "heatmap:cell:0:value" in keys

    snapshot = chart.accessibility_snapshot()
    assert snapshot.value_text == "2 by 2 heatmap"
    assert snapshot.children[1].name == "Mon, GPU"
    assert snapshot.children[1].value == 0.75


def test_radar_chart_builds_retained_fill_outline_spokes_and_markers() -> None:
    chart = RadarChart(
        _radar_series(),
        bounds=Rect(0.0, 0.0, 460.0, 320.0),
        key="radar",
        title="Engine profile",
        max_value=10.0,
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}
    paths = [node for node in scene.walk() if node.kind is SceneNodeKind.PATH]

    assert chart.value_max == 10.0
    assert "radar:ring:4:0" in keys
    assert "radar:spoke:3" in keys
    assert "radar:series:0:fill" in keys
    assert "radar:series:1:outline:3" in keys
    assert "radar:series:1:point:2" in keys
    assert paths

    snapshot = chart.accessibility_snapshot()
    assert snapshot.value_text == "2 series"
    assert snapshot.children[1].children[1].name == "GPU"
    assert snapshot.children[1].children[1].value == 9.0


def test_advanced_charts_validate_identity_numeric_and_domain_contracts() -> None:
    with pytest.raises(ValueError, match="finite"):
        ScatterPoint("bad", "Bad", math.inf, 1.0)
    with pytest.raises(ValueError, match="Duplicate scatter point key"):
        ScatterSeries(
            "duplicate",
            "Duplicate",
            (
                ScatterPoint("same", "A", 1.0, 1.0),
                ScatterPoint("same", "B", 2.0, 2.0),
            ),
        )
    with pytest.raises(ValueError, match="Duplicate heatmap coordinate"):
        HeatmapChart(
            (
                HeatmapCell("a", "Mon", "CPU", 1.0),
                HeatmapCell("b", "Mon", "CPU", 2.0),
            ),
            bounds=Rect(0.0, 0.0, 240.0, 160.0),
        )
    with pytest.raises(ValueError, match="ordered categories"):
        RadarChart(
            (
                _radar_series()[0],
                ChartSeries(
                    "wrong",
                    "Wrong",
                    (
                        ChartPoint("cpu", "CPU", 1.0),
                        ChartPoint("memory", "Memory", 2.0),
                        ChartPoint("gpu", "GPU", 3.0),
                        ChartPoint("io", "I/O", 4.0),
                    ),
                ),
            ),
            bounds=Rect(0.0, 0.0, 320.0, 240.0),
        )
    with pytest.raises(ValueError, match="non-negative"):
        RadarChart(
            (
                ChartSeries(
                    "negative",
                    "Negative",
                    (
                        ChartPoint("a", "A", 1.0),
                        ChartPoint("b", "B", -1.0),
                        ChartPoint("c", "C", 2.0),
                    ),
                ),
            ),
            bounds=Rect(0.0, 0.0, 320.0, 240.0),
        )
