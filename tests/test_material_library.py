import math

import pytest

from swirui import FUTURE_LIGHT, SilkRibbon, StreamingAreaChart, StreamingChartSeries
from swirui.rendering import Path2D, Point, Rect
from swirui.widgets import ChartPoint


def test_band_tessellation_covers_each_cell_once():
    top = (Point(0, 1), Point(2, 0), Point(5, 2))
    bottom = (Point(0, 2), Point(2, 4), Point(5, 3))
    band = Path2D.horizontal_band(top, bottom)
    assert band.points == (*top, *reversed(bottom))
    assert band.triangle_count == 4
    areas = [(b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)
             for a, b, c in band.triangulate()]
    assert min(areas) > 0 and sum(areas) / 2 == pytest.approx(12.5)
    for invalid in ((), top, bottom[::-1], (*bottom[:2], Point(4, 5)),
                    (*bottom[:2], Point(5, math.nan))):
        with pytest.raises(ValueError):
            Path2D.horizontal_band(top, invalid)


def test_ribbon_recolors_without_retessellation_or_pointer_targets():
    ribbon = SilkRibbon(bounds=Rect(3, 12, 320, 104))
    initial = ribbon.build_scene_node()
    ribbon.theme = FUTURE_LIGHT.with_accent("#F5AF12")
    tinted = ribbon.build_scene_node()
    assert all(a.path is b.path for a, b in zip(initial.children, tinted.children, strict=True))
    assert initial.children[12].fill != tinted.children[12].fill
    assert all(not node.hit_testable for node in tinted.walk())
    ribbon.bounds = Rect(0, 0, 0, 104)
    assert not ribbon.build_scene_node().children


def test_streaming_area_uses_new_sample_and_retains_pause_semantics():
    series = StreamingChartSeries("s", "Signal", [ChartPoint(0, "a", -2)], capacity=3)
    chart = StreamingAreaChart([series], bounds=Rect(0, 0, 440, 200))
    chart.pause()
    chart.append("s", ChartPoint(1, "b", 4))
    assert len(chart.series[0].points) == 1
    chart.resume()
    fills = [node for node in chart.build_scene_node().walk() if ":area:" in node.key]
    assert len(fills) == 2  # The segment crosses zero and has a fill on each side.
    assert all(node.path and node.path.triangle_count == 1 for node in fills)
