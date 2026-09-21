"""Retained line and area chart implementations."""

from __future__ import annotations

import math
from collections.abc import Sequence

from swirui.rendering import Color, Path2D, Point, Rect, SceneNode, SceneNodeKind

from .cartesian_chart import CartesianChart, EPSILON, rectangle_node


class LineChart(CartesianChart):
    """Multi-series line chart rendered through retained GPU path primitives."""

    chart_kind = "line"

    def add_data_nodes(self, root: SceneNode, plot: Rect, low: float, high: float) -> None:
        for series_index, series in enumerate(self.series):
            color = self.series_color(series_index)
            points = tuple(
                Point(
                    self.x_position(index, len(series.points), plot),
                    self.value_y(point.value, plot, low, high),
                )
                for index, point in enumerate(series.points)
            )
            add_line_series(root, self.key, series_index, points, color)


class AreaChart(LineChart):
    """Multi-series zero-baseline area chart with retained line outlines."""

    include_zero = True
    chart_kind = "area"

    def add_data_nodes(self, root: SceneNode, plot: Rect, low: float, high: float) -> None:
        baseline = self.value_y(0.0, plot, low, high)
        for series_index, series in enumerate(self.series):
            color = self.series_color(series_index)
            points = tuple(
                Point(
                    self.x_position(index, len(series.points), plot),
                    self.value_y(point.value, plot, low, high),
                )
                for index, point in enumerate(series.points)
            )
            for index, (start, end) in enumerate(zip(points, points[1:], strict=False)):
                add_area_segment(
                    root,
                    self.key,
                    series_index,
                    index,
                    start,
                    end,
                    series.points[index].value,
                    series.points[index + 1].value,
                    baseline,
                    color.with_alpha(0.25),
                )
            add_line_series(root, self.key, series_index, points, color)


def add_line_series(
    root: SceneNode,
    chart_key: str,
    series_index: int,
    points: tuple[Point, ...],
    color: Color,
) -> None:
    for index, (start, end) in enumerate(zip(points, points[1:], strict=False)):
        node = segment_node(
            f"{chart_key}:series:{series_index}:line:{index}",
            start,
            end,
            color,
        )
        if node is not None:
            root.add(node)
    for index, point in enumerate(points):
        root.add(
            rectangle_node(
                f"{chart_key}:series:{series_index}:point:{index}",
                Rect(point.x - 3.5, point.y - 3.5, 7.0, 7.0),
                color,
                radius=3.5,
            )
        )


def segment_node(key: str, start: Point, end: Point, color: Color) -> SceneNode | None:
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy)
    if length <= EPSILON:
        return None
    nx = -dy / length
    ny = dx / length
    return polygon_node(
        key,
        (
            Point(start.x + nx, start.y + ny),
            Point(end.x + nx, end.y + ny),
            Point(end.x - nx, end.y - ny),
            Point(start.x - nx, start.y - ny),
        ),
        color,
    )


def add_area_segment(
    root: SceneNode,
    chart_key: str,
    series_index: int,
    segment_index: int,
    start: Point,
    end: Point,
    start_value: float,
    end_value: float,
    baseline: float,
    color: Color,
) -> None:
    if start_value * end_value < 0.0:
        ratio = -start_value / (end_value - start_value)
        crossing = Point(start.x + (end.x - start.x) * ratio, baseline)
        parts = (
            ("a", (start, crossing, Point(start.x, baseline))),
            ("b", (crossing, end, Point(end.x, baseline))),
        )
        for suffix, points in parts:
            node = polygon_node(
                f"{chart_key}:series:{series_index}:area:{segment_index}:{suffix}",
                points,
                color,
            )
            if node is not None:
                root.add(node)
        return
    node = polygon_node(
        f"{chart_key}:series:{series_index}:area:{segment_index}",
        (start, end, Point(end.x, baseline), Point(start.x, baseline)),
        color,
    )
    if node is not None:
        root.add(node)


def polygon_node(key: str, points: Sequence[Point], color: Color) -> SceneNode | None:
    clean: list[Point] = []
    for point in points:
        if not clean or point != clean[-1]:
            clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    if len(clean) < 3:
        return None
    left = min(point.x for point in clean)
    top = min(point.y for point in clean)
    right = max(point.x for point in clean)
    bottom = max(point.y for point in clean)
    if right - left <= EPSILON or bottom - top <= EPSILON:
        return None
    local = tuple(Point(point.x - left, point.y - top) for point in clean)
    try:
        path = Path2D(local)
    except ValueError:
        return None
    return SceneNode(
        key=key,
        kind=SceneNodeKind.PATH,
        bounds=Rect(left, top, right - left, bottom - top),
        fill=color,
        path=path,
        hit_testable=False,
    )
