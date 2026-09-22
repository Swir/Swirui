from __future__ import annotations

from swirui import BarChart, ChartPoint, ChartSeries, LineChart
from swirui.rendering import Rect


POINT_COUNT = 100_000


def _large_series(count: int = POINT_COUNT) -> ChartSeries:
    return ChartSeries(
        "telemetry",
        "Telemetry",
        tuple(
            ChartPoint(index, f"P{index}", float(((index * 37) % 997) - 498))
            for index in range(count)
        ),
    )


def test_large_line_scene_is_bounded_and_shape_preserving() -> None:
    series = _large_series()
    chart = LineChart(
        (series,),
        bounds=Rect(0.0, 0.0, 1_280.0, 520.0),
        key="large-line",
        max_render_points=512,
        accessibility_point_limit=64,
    )

    indices = chart.render_indices(0)
    repeated = chart.render_indices(0)
    scene = chart.build_scene_node()
    keys = {node.key for node in scene.walk()}
    series_nodes = [node for node in scene.walk() if node.key.startswith("large-line:series:0:")]

    assert indices is repeated
    assert len(indices) <= 512
    assert indices[0] == 0
    assert indices[-1] == POINT_COUNT - 1
    assert f"large-line:series:0:point:{indices[0]}" in keys
    assert f"large-line:series:0:point:{indices[-1]}" in keys
    assert len(series_nodes) <= 1_023


def test_large_chart_zoom_keeps_projection_bounded_and_selection_exact() -> None:
    series = _large_series()
    chart = LineChart(
        (series,),
        bounds=Rect(0.0, 0.0, 1_200.0, 500.0),
        key="large-zoom",
        max_render_points=384,
    )

    chart.zoom(20.0, anchor_x=0.5, anchor_y=0.5)
    indices = chart.render_indices(0)
    selected_index = round((chart.viewport.x_min + chart.viewport.x_max) / 2.0)
    position = chart.point_position(
        0,
        selected_index,
        chart.plot_bounds,
        chart.viewport.y_min,
        chart.viewport.y_max,
    )
    selection = chart.select_nearest(position.x, position.y, max_distance=2.0)

    assert len(indices) <= 384
    assert selection is not None
    assert selection.point_index == selected_index


def test_large_accessibility_projection_is_bounded_and_preserves_selection() -> None:
    series = _large_series()
    chart = LineChart(
        (series,),
        bounds=Rect(0.0, 0.0, 1_100.0, 480.0),
        key="large-accessibility",
        max_render_points=256,
        accessibility_point_limit=48,
    )
    selected_index = 54_321
    chart.select(0, selected_index)

    snapshot = chart.accessibility_snapshot()
    series_node = snapshot.children[0]
    child_keys = {node.key for node in series_node.children}

    assert len(series_node.children) <= 48
    assert f"large-accessibility:series:0:point:{selected_index}" in child_keys
    assert f"{POINT_COUNT} data points" in (snapshot.value_text or "")
    assert "representative nodes" in (series_node.description or "")


def test_large_bar_scene_uses_same_bounded_projection() -> None:
    series = _large_series(50_000)
    chart = BarChart(
        (series,),
        bounds=Rect(0.0, 0.0, 1_200.0, 480.0),
        key="large-bar",
        max_render_points=320,
    )

    scene = chart.build_scene_node()
    bars = [node for node in scene.walk() if node.key.startswith("large-bar:series:0:bar:")]

    assert len(chart.render_indices(0)) <= 320
    assert len(bars) <= 320


def test_large_dataset_limits_validate_without_changing_full_data_contract() -> None:
    series = _large_series(20)
    chart = LineChart(
        (series,),
        bounds=Rect(0.0, 0.0, 500.0, 240.0),
        max_render_points=None,
        accessibility_point_limit=8,
    )

    assert len(chart.series[0].points) == 20
    assert chart.render_indices(0) == tuple(range(20))

    try:
        LineChart((series,), bounds=Rect(0.0, 0.0, 500.0, 240.0), max_render_points=4)
    except ValueError as error:
        assert "at least 8" in str(error)
    else:
        raise AssertionError("max_render_points below the supported minimum must fail")
