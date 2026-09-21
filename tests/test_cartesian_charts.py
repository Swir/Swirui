from __future__ import annotations

import math

import pytest

from swirui import AreaChart, BarChart, ChartPoint, ChartSeries, LineChart
from swirui.core import AccessibilityRole
from swirui.rendering import Rect, SceneNodeKind


def _series() -> tuple[ChartSeries, ...]:
    return (
        ChartSeries(
            "downloads",
            "Downloads",
            (
                ChartPoint("mon", "Mon", 12.0),
                ChartPoint("tue", "Tue", 22.0),
                ChartPoint("wed", "Wed", 16.0),
            ),
        ),
        ChartSeries(
            "installs",
            "Installs",
            (
                ChartPoint("mon", "Mon", 8.0),
                ChartPoint("tue", "Tue", 14.0),
                ChartPoint("wed", "Wed", 19.0),
            ),
        ),
    )


def test_line_chart_builds_retained_paths_markers_axes_and_labels() -> None:
    chart = LineChart(
        _series(),
        bounds=Rect(20.0, 30.0, 560.0, 280.0),
        key="line",
        title="Package activity",
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}
    paths = [node for node in scene.walk() if node.kind is SceneNodeKind.PATH]

    assert "line:title" in keys
    assert "line:axis:x" in keys
    assert "line:series:0:point:2" in keys
    assert "line:series:1:line:1" in keys
    assert len(paths) == 4
    assert chart.y_domain == (8.0, 22.0)


def test_area_chart_splits_zero_crossing_fill_without_invalid_polygon() -> None:
    chart = AreaChart(
        (
            ChartSeries(
                "delta",
                "Delta",
                (
                    ChartPoint("a", "A", -4.0),
                    ChartPoint("b", "B", 6.0),
                    ChartPoint("c", "C", 3.0),
                ),
            ),
        ),
        bounds=Rect(0.0, 0.0, 420.0, 240.0),
        key="area",
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}

    assert chart.y_domain == (-4.0, 6.0)
    assert "area:series:0:area:0:a" in keys
    assert "area:series:0:area:0:b" in keys
    assert "area:series:0:area:1" in keys


def test_bar_chart_groups_series_and_uses_zero_baseline() -> None:
    chart = BarChart(
        _series(),
        bounds=Rect(0.0, 0.0, 500.0, 260.0),
        key="bar",
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}

    assert chart.y_domain == (0.0, 22.0)
    assert "bar:series:0:bar:0" in keys
    assert "bar:series:1:bar:2" in keys
    assert "bar:x:2" in keys


def test_chart_series_replacement_and_accessibility_are_python_first() -> None:
    chart = LineChart(
        _series(),
        bounds=Rect(0.0, 0.0, 460.0, 240.0),
        key="accessible-chart",
    )
    chart.set_series((_series()[1],))

    snapshot = chart.accessibility_snapshot()

    assert [series.key for series in chart.series] == ["installs"]
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.value_text == "1 series"
    assert snapshot.children[0].role is AccessibilityRole.LIST
    assert snapshot.children[0].name == "Installs"
    assert snapshot.children[0].children[1].name == "Tue"
    assert snapshot.children[0].children[1].value == 14.0


def test_charts_validate_identity_numeric_and_domain_contracts() -> None:
    with pytest.raises(ValueError, match="finite"):
        ChartPoint("bad", "Bad", math.inf)
    with pytest.raises(ValueError, match="Duplicate chart point key"):
        ChartSeries(
            "duplicate-points",
            "Duplicate points",
            (ChartPoint("same", "A", 1.0), ChartPoint("same", "B", 2.0)),
        )
    with pytest.raises(ValueError, match="Duplicate chart series key"):
        LineChart(
            (_series()[0], _series()[0]),
            bounds=Rect(0.0, 0.0, 320.0, 180.0),
        )
    with pytest.raises(ValueError, match="smaller"):
        LineChart(
            _series(),
            bounds=Rect(0.0, 0.0, 320.0, 180.0),
            y_min=10.0,
            y_max=10.0,
        )
