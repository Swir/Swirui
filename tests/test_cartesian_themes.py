from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    AreaChart,
    BarChart,
    ChartPoint,
    ChartSeries,
    LineChart,
    Panel,
)
from swirui.rendering import Color, Rect, SceneNodeKind
from swirui.widgets.cartesian_chart import BACKGROUND, PALETTE, TEXT


@pytest.mark.parametrize("chart_type", [LineChart, AreaChart, BarChart])
def test_chart_theme_switch_preserves_view_selection_and_explicit_series_color(chart_type):
    explicit = Color(.2, .3, .4)
    points = tuple(ChartPoint(i, str(i), 10 + i * 4) for i in range(10))
    chart = chart_type([
        ChartSeries("a", "Automatic", points), ChartSeries("b", "Authored", points, explicit),
    ], bounds=Rect(0, 0, 600, 300), title="Activity")
    root = Panel(bounds=chart.bounds, theme=FUTURE_DARK)
    root.add(chart)
    selection = chart.select(0, 5)
    viewport = chart.zoom(2)
    chart.emit("focus_gained")
    light = replace(FUTURE_LIGHT, font_family="Arial")
    for theme in (light, FUTURE_DARK):
        root.theme = theme
        scene = chart.build_scene_node()
        nodes = {node.key: node for node in scene.walk()}
        assert scene.fill == theme.surface_color("surface")
        assert chart.series_color(0) == theme.surface_color("accent")
        assert chart.series_color(1) == explicit
        labels = [node for node in nodes.values() if node.kind == SceneNodeKind.TEXT]
        assert any(":x:" in node.key for node in labels)
        assert all(node.fill == theme.text_color("muted") for node in labels)
        assert all(node.font_family == theme.font_family for node in labels)
        assert nodes[f"{chart.key}:focus:top"].fill == theme.surface_color("focus")
        assert chart.selection == selection
        assert chart.viewport == viewport
    chart.theme = light
    root.theme = FUTURE_DARK
    assert chart.build_scene_node().fill == light.surface_color("surface")
    chart.theme = None
    root.remove(chart)
    scene = chart.build_scene_node()
    assert scene.fill == BACKGROUND
    assert chart.series_color(0) == PALETTE[0]
    assert all(n.fill == TEXT for n in scene.walk() if n.kind == SceneNodeKind.TEXT)
