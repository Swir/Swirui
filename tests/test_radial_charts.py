from __future__ import annotations

import math

import pytest

from swirui import ChartPoint, ChartSeries, DonutChart, PieChart
from swirui.core import AccessibilityRole
from swirui.rendering import Color, Rect, SceneNodeKind


def _series(values: tuple[float, ...] = (10.0, 20.0, 30.0, 40.0)) -> ChartSeries:
    labels = ("Docs", "Search", "Direct", "Social")
    return ChartSeries(
        "traffic",
        "Traffic",
        tuple(
            ChartPoint(f"slice-{index}", label, value)
            for index, (label, value) in enumerate(zip(labels, values, strict=True))
        ),
    )


def test_pie_chart_builds_retained_gpu_path_segments_and_legend() -> None:
    chart = PieChart(
        _series(),
        bounds=Rect(20.0, 30.0, 560.0, 300.0),
        key="pie",
        title="Traffic sources",
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}
    paths = [node for node in scene.walk() if node.kind is SceneNodeKind.PATH]

    assert "pie:title" in keys
    assert "pie:slice:0:segment:0" in keys
    assert "pie:slice:3:segment:0" in keys
    assert "pie:legend:0:swatch" in keys
    assert "pie:legend:3:label" in keys
    assert len(paths) == 48
    assert chart.total == pytest.approx(100.0)


def test_donut_chart_uses_configured_inner_radius_and_compact_layout() -> None:
    chart = DonutChart(
        _series(),
        bounds=Rect(0.0, 0.0, 320.0, 220.0),
        key="donut",
        inner_radius_ratio=0.62,
    )

    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}

    assert chart.inner_radius_ratio == pytest.approx(0.62)
    assert "donut:slice:1:segment:0" in keys
    assert not any(key.startswith("donut:legend:") for key in keys)


def test_radial_chart_accessibility_reports_slice_values_and_percentages() -> None:
    chart = DonutChart(
        _series(),
        bounds=Rect(0.0, 0.0, 520.0, 280.0),
        key="accessible-donut",
        title="Traffic",
    )

    snapshot = chart.accessibility_snapshot()

    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.name == "Traffic"
    assert snapshot.value_text == "4 slices"
    assert snapshot.children[0].role is AccessibilityRole.LIST
    assert snapshot.children[0].name == "Traffic"
    assert snapshot.children[0].children[2].name == "Direct"
    assert snapshot.children[0].children[2].value == 30.0
    assert snapshot.children[0].children[2].value_text == "30 (30.0%)"


def test_radial_chart_series_replacement_preserves_python_first_data_contract() -> None:
    chart = PieChart(
        _series(),
        bounds=Rect(0.0, 0.0, 480.0, 260.0),
        key="replace-pie",
    )
    replacement = ChartSeries(
        "traffic-next",
        "Traffic next",
        (
            ChartPoint("a", "A", 2.0),
            ChartPoint("b", "B", 6.0),
        ),
    )

    chart.set_series(replacement)

    assert chart.series is replacement
    assert chart.total == pytest.approx(8.0)
    keys = {node.key for node in chart.build_scene_node().walk()}
    assert "replace-pie:slice:1:segment:0" in keys
    assert not any(key.startswith("replace-pie:slice:2:") for key in keys)


def test_radial_charts_validate_values_geometry_and_color_contracts() -> None:
    bounds = Rect(0.0, 0.0, 360.0, 220.0)
    with pytest.raises(ValueError, match="non-negative"):
        PieChart(_series((10.0, -1.0, 2.0, 3.0)), bounds=bounds)
    with pytest.raises(ValueError, match="positive total"):
        DonutChart(_series((0.0, 0.0, 0.0, 0.0)), bounds=bounds)
    with pytest.raises(ValueError, match="inner_radius_ratio"):
        DonutChart(_series(), bounds=bounds, inner_radius_ratio=1.0)
    with pytest.raises(ValueError, match="finite"):
        PieChart(_series(), bounds=bounds, start_angle=math.inf)
    with pytest.raises(ValueError, match="colors"):
        PieChart(
            _series(),
            bounds=bounds,
            colors=(Color.from_hex("#38BDF8"),),
        )
