"""Retained scatter, heatmap and radar chart implementations."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from swirui.core import AccessibilityNode, AccessibilityRole
from swirui.rendering import Color, Point, Rect, SceneNode

from .base import Widget
from .cartesian_chart import (
    BACKGROUND,
    EPSILON,
    GRID,
    PALETTE,
    TEXT,
    format_value,
    rectangle_node,
    text_node,
)
from .charts import ChartSeries
from .line_area_chart import polygon_node, segment_node

HEATMAP_PALETTE = tuple(
    Color.from_hex(value)
    for value in ("#172554", "#1E3A8A", "#0369A1", "#0891B2", "#14B8A6", "#84CC16", "#FACC15")
)


@dataclass(frozen=True, slots=True)
class ScatterPoint:
    """One stable labelled two-dimensional sample."""

    key: Hashable
    label: str
    x: float
    y: float

    def __post_init__(self) -> None:
        hash(self.key)
        label = self.label.strip()
        x = float(self.x)
        y = float(self.y)
        if not label:
            raise ValueError("ScatterPoint label must not be empty.")
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("ScatterPoint coordinates must be finite.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)


@dataclass(frozen=True, slots=True)
class ScatterSeries:
    """Stable named scatter series with an optional explicit color."""

    key: Hashable
    name: str
    points: Sequence[ScatterPoint]
    color: Color | None = None

    def __post_init__(self) -> None:
        hash(self.key)
        name = self.name.strip()
        points = tuple(self.points)
        if not name:
            raise ValueError("ScatterSeries name must not be empty.")
        if not points:
            raise ValueError("ScatterSeries requires at least one point.")
        keys: set[Hashable] = set()
        for point in points:
            if point.key in keys:
                raise ValueError(f"Duplicate scatter point key: {point.key!r}")
            keys.add(point.key)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True)
class HeatmapCell:
    """One stable row/column heatmap value."""

    key: Hashable
    row: str
    column: str
    value: float

    def __post_init__(self) -> None:
        hash(self.key)
        row = self.row.strip()
        column = self.column.strip()
        value = float(self.value)
        if not row or not column:
            raise ValueError("HeatmapCell row and column must not be empty.")
        if not math.isfinite(value):
            raise ValueError("HeatmapCell value must be finite.")
        object.__setattr__(self, "row", row)
        object.__setattr__(self, "column", column)
        object.__setattr__(self, "value", value)


class ScatterChart(Widget):
    """Multi-series retained scatter chart with independent numeric x/y domains."""

    def __init__(
        self,
        series: Sequence[ScatterSeries],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> None:
        normalized_title = _title(title)
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or self.__class__.__name__,
        )
        self._series = _validate_scatter_series(series)
        self._title = normalized_title
        self._x_min = _finite_optional(x_min, "x_min")
        self._x_max = _finite_optional(x_max, "x_max")
        self._y_min = _finite_optional(y_min, "y_min")
        self._y_max = _finite_optional(y_max, "y_max")
        _validate_domain_pair(self._x_min, self._x_max, "x")
        _validate_domain_pair(self._y_min, self._y_max, "y")

    @property
    def series(self) -> tuple[ScatterSeries, ...]:
        return self._series

    @property
    def x_domain(self) -> tuple[float, float]:
        values = [point.x for series in self.series for point in series.points]
        return _domain(values, self._x_min, self._x_max)

    @property
    def y_domain(self) -> tuple[float, float]:
        values = [point.y for series in self.series for point in series.points]
        return _domain(values, self._y_min, self._y_max)

    @property
    def plot_bounds(self) -> Rect:
        top = self.bounds.y + (36.0 if self._title else 14.0)
        return Rect(
            self.bounds.x + 52.0,
            top,
            max(0.0, self.bounds.width - 66.0),
            max(0.0, self.bounds.bottom - top - 34.0),
        )

    def set_series(self, series: Sequence[ScatterSeries]) -> None:
        normalized = _validate_scatter_series(series)
        if normalized != self._series:
            self._series = normalized
            self.invalidate(reason="scatter_series")

    def build_scene_node(self) -> SceneNode:
        root = _chart_root(self.key, self.bounds, self._title)
        plot = self.plot_bounds
        if plot.width <= 0.0 or plot.height <= 0.0:
            return root
        x_low, x_high = self.x_domain
        y_low, y_high = self.y_domain
        for index in range(5):
            fraction = index / 4.0
            x = plot.x + fraction * plot.width
            y = plot.bottom - fraction * plot.height
            root.add(
                rectangle_node(
                    f"{self.key}:grid:x:{index}",
                    Rect(x, plot.y, 1.0, plot.height),
                    GRID,
                )
            )
            root.add(
                rectangle_node(
                    f"{self.key}:grid:y:{index}",
                    Rect(plot.x, y, plot.width, 1.0),
                    GRID,
                )
            )
            root.add(
                text_node(
                    f"{self.key}:x:{index}",
                    Rect(x - 28.0, plot.bottom + 7.0, 56.0, 15.0),
                    format_value(x_low + fraction * (x_high - x_low)),
                    10.0,
                )
            )
            root.add(
                text_node(
                    f"{self.key}:y:{index}",
                    Rect(self.bounds.x + 4.0, y - 7.0, 44.0, 14.0),
                    format_value(y_low + fraction * (y_high - y_low)),
                    10.0,
                )
            )
        root.add(
            rectangle_node(
                f"{self.key}:axis:x",
                Rect(plot.x, plot.bottom, plot.width, 1.0),
                TEXT,
            )
        )
        root.add(rectangle_node(f"{self.key}:axis:y", Rect(plot.x, plot.y, 1.0, plot.height), TEXT))
        for series_index, series in enumerate(self.series):
            color = series.color or PALETTE[series_index % len(PALETTE)]
            for point_index, point in enumerate(series.points):
                x = plot.x + (point.x - x_low) * plot.width / (x_high - x_low)
                y = plot.bottom - (point.y - y_low) * plot.height / (y_high - y_low)
                root.add(
                    rectangle_node(
                        f"{self.key}:series:{series_index}:point:{point_index}",
                        Rect(x - 4.0, y - 4.0, 8.0, 8.0),
                        color,
                        radius=4.0,
                    )
                )
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:series:{series_index}",
                role=AccessibilityRole.LIST,
                name=series.name,
                description="scatter chart series",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                children=tuple(
                    AccessibilityNode(
                        key=f"{self.key}:series:{series_index}:point:{point_index}",
                        role=AccessibilityRole.LIST_ITEM,
                        name=point.label,
                        description=f"x {format_value(point.x)}, y {format_value(point.y)}",
                        enabled=self.enabled,
                        focusable=False,
                        focused=False,
                        value=point.y,
                        value_text=f"{format_value(point.x)}, {format_value(point.y)}",
                    )
                    for point_index, point in enumerate(series.points)
                ),
            )
            for series_index, series in enumerate(self.series)
        )
        return _group_snapshot(self, f"{len(self.series)} series", children)


class HeatmapChart(Widget):
    """Retained matrix heatmap with deterministic labels and color buckets."""

    def __init__(
        self,
        cells: Sequence[HeatmapCell],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        normalized_title = _title(title)
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or self.__class__.__name__,
        )
        self._cells = _validate_heatmap_cells(cells)
        self._title = normalized_title
        self._min_value = _finite_optional(min_value, "min_value")
        self._max_value = _finite_optional(max_value, "max_value")
        _validate_domain_pair(self._min_value, self._max_value, "heatmap")

    @property
    def cells(self) -> tuple[HeatmapCell, ...]:
        return self._cells

    @property
    def rows(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(cell.row for cell in self.cells))

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(cell.column for cell in self.cells))

    @property
    def value_domain(self) -> tuple[float, float]:
        values = [cell.value for cell in self.cells]
        low = min(values) if self._min_value is None else self._min_value
        high = max(values) if self._max_value is None else self._max_value
        if low > high:
            raise ValueError("Configured heatmap value domain is invalid.")
        return low, high

    def set_cells(self, cells: Sequence[HeatmapCell]) -> None:
        normalized = _validate_heatmap_cells(cells)
        if normalized != self._cells:
            self._cells = normalized
            self.invalidate(reason="heatmap_cells")

    def build_scene_node(self) -> SceneNode:
        root = _chart_root(self.key, self.bounds, self._title)
        rows = self.rows
        columns = self.columns
        top = self.bounds.y + (38.0 if self._title else 16.0)
        plot = Rect(
            self.bounds.x + 72.0,
            top,
            max(0.0, self.bounds.width - 84.0),
            max(0.0, self.bounds.bottom - top - 34.0),
        )
        if plot.width <= 0.0 or plot.height <= 0.0:
            return root
        cell_width = plot.width / len(columns)
        cell_height = plot.height / len(rows)
        row_index = {value: index for index, value in enumerate(rows)}
        column_index = {value: index for index, value in enumerate(columns)}
        low, high = self.value_domain
        for index, row in enumerate(rows):
            y = plot.y + (index + 0.5) * cell_height
            root.add(
                text_node(
                    f"{self.key}:row:{index}",
                    Rect(self.bounds.x + 6.0, y - 7.0, 62.0, 14.0),
                    row,
                    10.0,
                )
            )
        for index, column in enumerate(columns):
            x = plot.x + (index + 0.5) * cell_width
            root.add(
                text_node(
                    f"{self.key}:column:{index}",
                    Rect(x - cell_width * 0.45, plot.bottom + 7.0, cell_width * 0.9, 15.0),
                    column,
                    10.0,
                )
            )
        for cell_index, cell in enumerate(self.cells):
            row = row_index[cell.row]
            column = column_index[cell.column]
            bounds = Rect(
                plot.x + column * cell_width + 1.0,
                plot.y + row * cell_height + 1.0,
                max(0.0, cell_width - 2.0),
                max(0.0, cell_height - 2.0),
            )
            root.add(
                rectangle_node(
                    f"{self.key}:cell:{cell_index}",
                    bounds,
                    _heat_color(cell.value, low, high),
                    radius=min(4.0, min(bounds.width, bounds.height) / 6.0),
                )
            )
            if cell_width >= 48.0 and cell_height >= 26.0:
                root.add(
                    text_node(
                        f"{self.key}:cell:{cell_index}:value",
                        Rect(
                            bounds.x + 3.0,
                            bounds.y + bounds.height / 2.0 - 7.0,
                            max(0.0, bounds.width - 6.0),
                            14.0,
                        ),
                        format_value(cell.value),
                        10.0,
                    )
                )
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:cell:{index}",
                role=AccessibilityRole.LIST_ITEM,
                name=f"{cell.row}, {cell.column}",
                description="heatmap cell",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                value=cell.value,
                value_text=format_value(cell.value),
            )
            for index, cell in enumerate(self.cells)
        )
        return _group_snapshot(self, f"{len(self.rows)} by {len(self.columns)} heatmap", children)


class RadarChart(Widget):
    """Multi-series radar chart rendered through retained path primitives."""

    def __init__(
        self,
        series: Sequence[ChartSeries],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        max_value: float | None = None,
    ) -> None:
        normalized_title = _title(title)
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or self.__class__.__name__,
        )
        self._series = _validate_radar_series(series)
        self._title = normalized_title
        self._max_value = _finite_optional(max_value, "max_value")
        if self._max_value is not None:
            if self._max_value <= 0.0:
                raise ValueError("max_value must be greater than zero.")
            data_max = max(point.value for item in self._series for point in item.points)
            if self._max_value < data_max:
                raise ValueError("max_value must cover every radar value.")

    @property
    def series(self) -> tuple[ChartSeries, ...]:
        return self._series

    @property
    def value_max(self) -> float:
        if self._max_value is not None:
            return self._max_value
        return max(1.0, max(point.value for item in self.series for point in item.points))

    def set_series(self, series: Sequence[ChartSeries]) -> None:
        normalized = _validate_radar_series(series)
        if self._max_value is not None:
            data_max = max(point.value for item in normalized for point in item.points)
            if data_max > self._max_value:
                raise ValueError("Configured max_value does not cover updated radar values.")
        if normalized != self._series:
            self._series = normalized
            self.invalidate(reason="radar_series")

    def build_scene_node(self) -> SceneNode:
        root = _chart_root(self.key, self.bounds, self._title)
        top = self.bounds.y + (34.0 if self._title else 12.0)
        available_height = max(0.0, self.bounds.bottom - top - 22.0)
        radius = max(0.0, min(self.bounds.width - 48.0, available_height) / 2.0)
        if radius <= 0.0:
            return root
        center = Point(self.bounds.x + self.bounds.width / 2.0, top + available_height / 2.0)
        labels = self.series[0].points
        angles = tuple(
            -math.pi / 2.0 + index * math.tau / len(labels)
            for index in range(len(labels))
        )
        for ring in range(1, 5):
            ring_radius = radius * ring / 4.0
            points = tuple(
                Point(
                    center.x + math.cos(angle) * ring_radius,
                    center.y + math.sin(angle) * ring_radius,
                )
                for angle in angles
            )
            _add_outline(root, f"{self.key}:ring:{ring}", points, GRID)
        for index, (label, angle) in enumerate(zip(labels, angles, strict=True)):
            edge = Point(center.x + math.cos(angle) * radius, center.y + math.sin(angle) * radius)
            spoke = segment_node(f"{self.key}:spoke:{index}", center, edge, GRID)
            if spoke is not None:
                root.add(spoke)
            label_center = Point(
                center.x + math.cos(angle) * (radius + 16.0),
                center.y + math.sin(angle) * (radius + 16.0),
            )
            root.add(
                text_node(
                    f"{self.key}:label:{index}",
                    Rect(label_center.x - 32.0, label_center.y - 7.0, 64.0, 14.0),
                    label.label,
                    10.0,
                )
            )
        maximum = self.value_max
        for series_index, series in enumerate(self.series):
            color = series.color or PALETTE[series_index % len(PALETTE)]
            points = tuple(
                Point(
                    center.x + math.cos(angles[index]) * radius * point.value / maximum,
                    center.y + math.sin(angles[index]) * radius * point.value / maximum,
                )
                for index, point in enumerate(series.points)
            )
            fill = polygon_node(
                f"{self.key}:series:{series_index}:fill",
                points,
                color.with_alpha(0.20),
            )
            if fill is not None:
                root.add(fill)
            _add_outline(root, f"{self.key}:series:{series_index}:outline", points, color)
            for point_index, point in enumerate(points):
                root.add(
                    rectangle_node(
                        f"{self.key}:series:{series_index}:point:{point_index}",
                        Rect(point.x - 3.5, point.y - 3.5, 7.0, 7.0),
                        color,
                        radius=3.5,
                    )
                )
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:series:{series_index}",
                role=AccessibilityRole.LIST,
                name=series.name,
                description="radar chart series",
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
        return _group_snapshot(self, f"{len(self.series)} series", children)


def _validate_scatter_series(series: Sequence[ScatterSeries]) -> tuple[ScatterSeries, ...]:
    normalized = tuple(series)
    if not normalized:
        raise ValueError("A scatter chart requires at least one series.")
    keys: set[Hashable] = set()
    for item in normalized:
        if item.key in keys:
            raise ValueError(f"Duplicate scatter series key: {item.key!r}")
        keys.add(item.key)
    return normalized


def _validate_heatmap_cells(cells: Sequence[HeatmapCell]) -> tuple[HeatmapCell, ...]:
    normalized = tuple(cells)
    if not normalized:
        raise ValueError("A heatmap chart requires at least one cell.")
    keys: set[Hashable] = set()
    coordinates: set[tuple[str, str]] = set()
    for cell in normalized:
        if cell.key in keys:
            raise ValueError(f"Duplicate heatmap cell key: {cell.key!r}")
        coordinate = (cell.row, cell.column)
        if coordinate in coordinates:
            raise ValueError(f"Duplicate heatmap coordinate: {coordinate!r}")
        keys.add(cell.key)
        coordinates.add(coordinate)
    return normalized


def _validate_radar_series(series: Sequence[ChartSeries]) -> tuple[ChartSeries, ...]:
    normalized = tuple(series)
    if not normalized:
        raise ValueError("A radar chart requires at least one series.")
    expected = tuple((point.key, point.label) for point in normalized[0].points)
    keys: set[Hashable] = set()
    for item in normalized:
        if item.key in keys:
            raise ValueError(f"Duplicate radar series key: {item.key!r}")
        keys.add(item.key)
        identity = tuple((point.key, point.label) for point in item.points)
        if identity != expected:
            raise ValueError("Radar series must share the same ordered categories.")
        if any(point.value < 0.0 for point in item.points):
            raise ValueError("Radar chart values must be non-negative.")
    if len(expected) < 3:
        raise ValueError("Radar charts require at least three categories.")
    return normalized


def _chart_root(key: str, bounds: Rect, title: str | None) -> SceneNode:
    root = rectangle_node(key, bounds, BACKGROUND, radius=8.0, clip_to_bounds=True)
    if title:
        root.add(
            text_node(
                f"{key}:title",
                Rect(bounds.x + 12.0, bounds.y + 8.0, max(0.0, bounds.width - 24.0), 20.0),
                title,
                14.0,
            )
        )
    return root


def _group_snapshot(
    widget: Widget,
    value_text: str,
    children: tuple[AccessibilityNode, ...],
) -> AccessibilityNode:
    return AccessibilityNode(
        key=widget.key,
        role=AccessibilityRole.GROUP,
        name=widget.accessible_name or widget.name,
        description=widget.accessible_description,
        enabled=widget.enabled,
        focusable=False,
        focused=False,
        value_text=value_text,
        children=children,
    )


def _add_outline(root: SceneNode, key: str, points: tuple[Point, ...], color: Color) -> None:
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        node = segment_node(f"{key}:{index}", start, end, color)
        if node is not None:
            root.add(node)


def _heat_color(value: float, low: float, high: float) -> Color:
    if math.isclose(low, high, abs_tol=EPSILON):
        return HEATMAP_PALETTE[len(HEATMAP_PALETTE) // 2]
    fraction = min(1.0, max(0.0, (value - low) / (high - low)))
    index = min(len(HEATMAP_PALETTE) - 1, int(fraction * len(HEATMAP_PALETTE)))
    return HEATMAP_PALETTE[index]


def _domain(
    values: Sequence[float],
    configured_low: float | None,
    configured_high: float | None,
) -> tuple[float, float]:
    low = min(values) if configured_low is None else configured_low
    high = max(values) if configured_high is None else configured_high
    if low > high:
        raise ValueError("Configured chart domain is invalid.")
    if math.isclose(low, high, abs_tol=EPSILON):
        padding = max(1.0, abs(low) * 0.1)
        low, high = low - padding, high + padding
    return low, high


def _finite_optional(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite when provided.")
    return normalized


def _validate_domain_pair(low: float | None, high: float | None, axis: str) -> None:
    if low is not None and high is not None and low >= high:
        raise ValueError(f"{axis} minimum must be smaller than maximum.")


def _title(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else None
    if normalized == "":
        raise ValueError("Chart title must not be empty.")
    return normalized


__all__ = [
    "HeatmapCell",
    "HeatmapChart",
    "RadarChart",
    "ScatterChart",
    "ScatterPoint",
    "ScatterSeries",
]
