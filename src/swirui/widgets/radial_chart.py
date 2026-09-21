"""Retained pie and donut charts built on SwirUI SceneGraph paths."""

from __future__ import annotations

import math
from collections.abc import Sequence

from swirui.core import AccessibilityNode, AccessibilityRole
from swirui.rendering import Color, Point, Rect, SceneNode

from .base import Widget
from .cartesian_chart import BACKGROUND, PALETTE, format_value, rectangle_node, text_node
from .charts import ChartSeries
from .line_area_chart import polygon_node

_TAU = math.tau
_EPSILON = 1.0e-9
_MAX_ARC_STEP = math.radians(7.5)


class _RadialChart(Widget):
    """Shared retained implementation for pie-family charts."""

    chart_kind = "radial"

    def __init__(
        self,
        series: ChartSeries,
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        start_angle: float = -90.0,
        inner_radius_ratio: float = 0.0,
        colors: Sequence[Color] | None = None,
    ) -> None:
        normalized_title = title.strip() if title is not None else None
        if normalized_title == "":
            raise ValueError("Chart title must not be empty.")
        normalized_angle = float(start_angle)
        if not math.isfinite(normalized_angle):
            raise ValueError("start_angle must be finite.")
        normalized_inner = float(inner_radius_ratio)
        if not 0.0 <= normalized_inner < 1.0:
            raise ValueError("inner_radius_ratio must be in the range [0, 1).")
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or self.__class__.__name__,
        )
        self._series = self._validate_series(series)
        self._title = normalized_title
        self._start_angle = math.radians(normalized_angle)
        self._inner_radius_ratio = normalized_inner
        self._colors = self._validate_colors(colors, len(self._series.points))

    @property
    def series(self) -> ChartSeries:
        return self._series

    @property
    def total(self) -> float:
        return sum(point.value for point in self._series.points)

    @property
    def inner_radius_ratio(self) -> float:
        return self._inner_radius_ratio

    def set_series(self, series: ChartSeries) -> None:
        normalized = self._validate_series(series)
        if self._colors is not None and len(self._colors) != len(normalized.points):
            raise ValueError("Configured radial chart colors must match the updated point count.")
        if normalized != self._series:
            self._series = normalized
            self.invalidate(reason="chart_series")

    def build_scene_node(self) -> SceneNode:
        root = rectangle_node(
            self.key,
            self.bounds,
            BACKGROUND,
            radius=8.0,
            clip_to_bounds=True,
        )
        if self._title:
            root.add(
                text_node(
                    f"{self.key}:title",
                    Rect(
                        self.bounds.x + 12.0,
                        self.bounds.y + 8.0,
                        max(0.0, self.bounds.width - 24.0),
                        20.0,
                    ),
                    self._title,
                    14.0,
                )
            )

        layout = self._radial_layout()
        if layout is None:
            return root
        center, outer_radius, legend_x, legend_width = layout
        inner_radius = outer_radius * self._inner_radius_ratio
        angle = self._start_angle
        total = self.total

        for point_index, point in enumerate(self._series.points):
            sweep = point.value / total * _TAU
            if sweep > _EPSILON:
                self._add_slice_segments(
                    root,
                    point_index,
                    center,
                    inner_radius,
                    outer_radius,
                    angle,
                    angle + sweep,
                    self._slice_color(point_index),
                )
            angle += sweep

        if legend_width > 0.0:
            self._add_legend(root, legend_x, legend_width)
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        total = self.total
        points = tuple(
            AccessibilityNode(
                key=f"{self.key}:slice:{index}",
                role=AccessibilityRole.LIST_ITEM,
                name=point.label,
                description=self._series.name,
                enabled=self.enabled,
                focusable=False,
                focused=False,
                value=point.value,
                value_text=f"{format_value(point.value)} ({point.value / total * 100.0:.1f}%)",
            )
            for index, point in enumerate(self._series.points)
        )
        series_node = AccessibilityNode(
            key=f"{self.key}:series",
            role=AccessibilityRole.LIST,
            name=self._series.name,
            description=f"{self.chart_kind} chart series",
            enabled=self.enabled,
            focusable=False,
            focused=False,
            children=points,
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=False,
            focused=False,
            value_text=f"{len(points)} slices",
            children=(series_node,),
        )

    def _radial_layout(self) -> tuple[Point, float, float, float] | None:
        content_top = self.bounds.y + (36.0 if self._title else 14.0)
        content_height = max(0.0, self.bounds.bottom - content_top - 14.0)
        if content_height <= 4.0 or self.bounds.width <= 4.0:
            return None

        show_legend = self.bounds.width >= 360.0
        legend_width = min(190.0, self.bounds.width * 0.38) if show_legend else 0.0
        chart_left = self.bounds.x + 14.0
        chart_right = self.bounds.right - 14.0 - (legend_width + 10.0 if show_legend else 0.0)
        chart_width = max(0.0, chart_right - chart_left)
        diameter = min(chart_width, content_height)
        if diameter <= 4.0:
            return None
        outer_radius = diameter / 2.0
        center = Point(chart_left + chart_width / 2.0, content_top + content_height / 2.0)
        legend_x = self.bounds.right - 14.0 - legend_width
        return center, outer_radius, legend_x, legend_width

    def _add_slice_segments(
        self,
        root: SceneNode,
        point_index: int,
        center: Point,
        inner_radius: float,
        outer_radius: float,
        start_angle: float,
        end_angle: float,
        color: Color,
    ) -> None:
        sweep = end_angle - start_angle
        segment_count = max(1, math.ceil(abs(sweep) / _MAX_ARC_STEP))
        for segment_index in range(segment_count):
            first = start_angle + sweep * segment_index / segment_count
            second = start_angle + sweep * (segment_index + 1) / segment_count
            outer_a = _polar(center, outer_radius, first)
            outer_b = _polar(center, outer_radius, second)
            points: tuple[Point, ...]
            if inner_radius <= _EPSILON:
                points = (center, outer_a, outer_b)
            else:
                inner_b = _polar(center, inner_radius, second)
                inner_a = _polar(center, inner_radius, first)
                points = (outer_a, outer_b, inner_b, inner_a)
            node = polygon_node(
                f"{self.key}:slice:{point_index}:segment:{segment_index}",
                points,
                color,
            )
            if node is not None:
                root.add(node)

    def _add_legend(self, root: SceneNode, x: float, width: float) -> None:
        available_top = self.bounds.y + (38.0 if self._title else 16.0)
        available_height = max(0.0, self.bounds.bottom - available_top - 12.0)
        max_items = max(0, int(available_height // 22.0))
        visible = min(len(self._series.points), max_items)
        total = self.total
        for index, point in enumerate(self._series.points[:visible]):
            y = available_top + index * 22.0
            root.add(
                rectangle_node(
                    f"{self.key}:legend:{index}:swatch",
                    Rect(x, y + 3.0, 10.0, 10.0),
                    self._slice_color(index),
                    radius=2.0,
                )
            )
            root.add(
                text_node(
                    f"{self.key}:legend:{index}:label",
                    Rect(x + 16.0, y, max(0.0, width - 16.0), 16.0),
                    f"{point.label} {point.value / total * 100.0:.1f}%",
                    10.0,
                )
            )
        remaining = len(self._series.points) - visible
        if remaining > 0 and max_items > 0:
            y = available_top + max(0, visible - 1) * 22.0
            root.add(
                text_node(
                    f"{self.key}:legend:more",
                    Rect(x, y, width, 16.0),
                    f"+{remaining} more",
                    10.0,
                )
            )

    def _slice_color(self, index: int) -> Color:
        if self._colors is not None:
            return self._colors[index]
        return PALETTE[index % len(PALETTE)]

    @staticmethod
    def _validate_series(series: ChartSeries) -> ChartSeries:
        if not isinstance(series, ChartSeries):
            raise TypeError("Radial charts require one ChartSeries.")
        if any(point.value < 0.0 for point in series.points):
            raise ValueError("Pie and donut chart values must be non-negative.")
        if sum(point.value for point in series.points) <= _EPSILON:
            raise ValueError("Pie and donut charts require a positive total value.")
        return series

    @staticmethod
    def _validate_colors(
        colors: Sequence[Color] | None,
        point_count: int,
    ) -> tuple[Color, ...] | None:
        if colors is None:
            return None
        normalized = tuple(colors)
        if len(normalized) != point_count:
            raise ValueError("Radial chart colors must match the point count.")
        return normalized


class PieChart(_RadialChart):
    """Retained pie chart using GPU-backed path wedges."""

    chart_kind = "pie"

    def __init__(
        self,
        series: ChartSeries,
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        start_angle: float = -90.0,
        colors: Sequence[Color] | None = None,
    ) -> None:
        super().__init__(
            series,
            bounds=bounds,
            key=key,
            title=title,
            start_angle=start_angle,
            inner_radius_ratio=0.0,
            colors=colors,
        )


class DonutChart(_RadialChart):
    """Retained donut chart with a configurable inner-radius ratio."""

    chart_kind = "donut"

    def __init__(
        self,
        series: ChartSeries,
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        start_angle: float = -90.0,
        inner_radius_ratio: float = 0.56,
        colors: Sequence[Color] | None = None,
    ) -> None:
        super().__init__(
            series,
            bounds=bounds,
            key=key,
            title=title,
            start_angle=start_angle,
            inner_radius_ratio=inner_radius_ratio,
            colors=colors,
        )


def _polar(center: Point, radius: float, angle: float) -> Point:
    return Point(
        center.x + math.cos(angle) * radius,
        center.y + math.sin(angle) * radius,
    )


__all__ = ["DonutChart", "PieChart"]
