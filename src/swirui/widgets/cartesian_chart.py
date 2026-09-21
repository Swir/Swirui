"""Shared retained foundation for cartesian charts."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence

from swirui.core import AccessibilityNode, AccessibilityRole
from swirui.rendering import Color, CornerRadius, Rect, SceneNode, SceneNodeKind

from .base import Widget
from .charts import ChartSeries

PALETTE = tuple(
    Color.from_hex(value)
    for value in ("#38BDF8", "#818CF8", "#34D399", "#F59E0B", "#F472B6", "#A78BFA")
)
BACKGROUND = Color.from_hex("#0B1220")
GRID = Color.from_hex("#243044")
TEXT = Color.from_hex("#CBD5E1")
EPSILON = 1.0e-9


class CartesianChart(Widget):
    """Axes, scaling, labels and accessibility shared by retained charts."""

    include_zero = False
    chart_kind = "cartesian"

    def __init__(
        self,
        series: Sequence[ChartSeries],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> None:
        normalized_title = title.strip() if title is not None else None
        if normalized_title == "":
            raise ValueError("Chart title must not be empty.")
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or self.__class__.__name__,
        )
        self._series = self._validate_series(series)
        self._title = normalized_title
        self._y_min = _finite_optional(y_min, "y_min")
        self._y_max = _finite_optional(y_max, "y_max")
        if self._y_min is not None and self._y_max is not None and self._y_min >= self._y_max:
            raise ValueError("y_min must be smaller than y_max.")

    @property
    def series(self) -> tuple[ChartSeries, ...]:
        return self._series

    @property
    def y_domain(self) -> tuple[float, float]:
        values = [point.value for series in self.series for point in series.points]
        low, high = min(values), max(values)
        if self.include_zero:
            low, high = min(low, 0.0), max(high, 0.0)
        if self._y_min is not None:
            low = self._y_min
        if self._y_max is not None:
            high = self._y_max
        if low > high:
            raise ValueError("Configured chart y-domain is invalid.")
        if math.isclose(low, high, abs_tol=EPSILON):
            padding = max(1.0, abs(low) * 0.1)
            low, high = low - padding, high + padding
        return low, high

    @property
    def plot_bounds(self) -> Rect:
        top = self.bounds.y + (36.0 if self._title else 14.0)
        return Rect(
            self.bounds.x + 50.0,
            top,
            max(0.0, self.bounds.width - 64.0),
            max(0.0, self.bounds.bottom - top - 32.0),
        )

    def set_series(self, series: Sequence[ChartSeries]) -> None:
        normalized = self._validate_series(series)
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
        plot = self.plot_bounds
        if plot.width <= 0.0 or plot.height <= 0.0:
            return root
        low, high = self.y_domain
        self._add_axes(root, plot, low, high)
        self.add_category_labels(root, plot)
        self.add_data_nodes(root, plot, low, high)
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        series_nodes = tuple(
            AccessibilityNode(
                key=f"{self.key}:series:{series_index}",
                role=AccessibilityRole.LIST,
                name=series.name,
                description=f"{self.chart_kind} chart series",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                children=tuple(
                    AccessibilityNode(
                        key=f"{self.key}:series:{series_index}:point:{point_index}",
                        role=AccessibilityRole.LIST_ITEM,
                        name=point.label,
                        description=series.name,
                        enabled=self.enabled,
                        focusable=False,
                        focused=False,
                        value=point.value,
                        value_text=format_value(point.value),
                    )
                    for point_index, point in enumerate(series.points)
                ),
            )
            for series_index, series in enumerate(self.series)
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=False,
            focused=False,
            value_text=f"{len(self.series)} series",
            children=series_nodes,
        )

    def add_category_labels(self, root: SceneNode, plot: Rect) -> None:
        points = self.series[0].points
        stride = max(1, math.ceil(len(points) / 8))
        for index, point in enumerate(points):
            if index % stride and index != len(points) - 1:
                continue
            x = self.x_position(index, len(points), plot)
            root.add(
                text_node(
                    f"{self.key}:x:{index}",
                    Rect(x - 38.0, plot.bottom + 7.0, 76.0, 15.0),
                    point.label,
                    10.0,
                )
            )

    def add_data_nodes(self, root: SceneNode, plot: Rect, low: float, high: float) -> None:
        raise NotImplementedError

    @staticmethod
    def x_position(index: int, count: int, plot: Rect) -> float:
        if count == 1:
            return plot.x + plot.width / 2.0
        return plot.x + index * plot.width / (count - 1)

    @staticmethod
    def value_y(value: float, plot: Rect, low: float, high: float) -> float:
        return plot.bottom - (value - low) * plot.height / (high - low)

    def series_color(self, index: int) -> Color:
        series = self.series[index]
        return series.color or PALETTE[index % len(PALETTE)]

    def _add_axes(self, root: SceneNode, plot: Rect, low: float, high: float) -> None:
        for index in range(5):
            fraction = index / 4.0
            y = plot.bottom - fraction * plot.height
            root.add(
                rectangle_node(
                    f"{self.key}:grid:{index}",
                    Rect(plot.x, y, plot.width, 1.0),
                    GRID,
                )
            )
            root.add(
                text_node(
                    f"{self.key}:y:{index}",
                    Rect(self.bounds.x + 4.0, y - 7.0, 42.0, 14.0),
                    format_value(low + fraction * (high - low)),
                    10.0,
                )
            )
        root.add(rectangle_node(f"{self.key}:axis:y", Rect(plot.x, plot.y, 1.0, plot.height), TEXT))
        baseline_value = 0.0 if low <= 0.0 <= high else low
        baseline = self.value_y(baseline_value, plot, low, high)
        root.add(
            rectangle_node(
                f"{self.key}:axis:x",
                Rect(plot.x, baseline, plot.width, 1.0),
                TEXT,
            )
        )

    @staticmethod
    def _validate_series(series: Sequence[ChartSeries]) -> tuple[ChartSeries, ...]:
        normalized = tuple(series)
        if not normalized:
            raise ValueError("A chart requires at least one series.")
        keys: set[Hashable] = set()
        for item in normalized:
            if item.key in keys:
                raise ValueError(f"Duplicate chart series key: {item.key!r}")
            keys.add(item.key)
        return normalized


def rectangle_node(
    key: str,
    bounds: Rect,
    color: Color,
    radius: float = 0.0,
    *,
    clip_to_bounds: bool = False,
) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.RECTANGLE,
        bounds=bounds,
        fill=color,
        corner_radius=CornerRadius.uniform(radius),
        clip_to_bounds=clip_to_bounds,
        hit_testable=False,
    )


def text_node(key: str, bounds: Rect, value: str, size: float) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.TEXT,
        bounds=bounds,
        fill=TEXT,
        text=value,
        font_size=size,
        hit_testable=False,
    )


def format_value(value: float) -> str:
    return f"{value:.4g}"


def _finite_optional(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite when provided.")
    return normalized
