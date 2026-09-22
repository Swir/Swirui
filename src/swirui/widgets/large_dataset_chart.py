"""Bounded retained rendering helpers for large cartesian chart datasets."""

from __future__ import annotations

import math
from collections.abc import Sequence

from swirui.core import AccessibilityNode, AccessibilityRole, Event
from swirui.rendering import Rect, SceneNode

from .cartesian_chart import EPSILON, CartesianChart, format_value, text_node
from .charts import ChartPoint, ChartSelection, ChartSeries

_DEFAULT_RENDER_POINT_LIMIT = 2_048
_DEFAULT_ACCESSIBILITY_POINT_LIMIT = 512
_MIN_SAMPLE_BUDGET = 8


class LargeDatasetCartesianChart(CartesianChart):
    """Cartesian chart base with bounded scene fan-out for large datasets.

    The public data model remains lossless. Only retained render/accessibility
    projection is sampled when a visible series exceeds its configured budget.
    """

    def __init__(
        self,
        series: Sequence[ChartSeries],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
        interactive: bool = True,
        max_render_points: int | None = _DEFAULT_RENDER_POINT_LIMIT,
        accessibility_point_limit: int = _DEFAULT_ACCESSIBILITY_POINT_LIMIT,
    ) -> None:
        self._max_render_points = _sample_budget(max_render_points, "max_render_points")
        access_limit = _sample_budget(accessibility_point_limit, "accessibility_point_limit")
        assert access_limit is not None
        self._accessibility_point_limit = access_limit
        self._y_domain_cache: tuple[float, float] | None = None
        self._render_index_cache: dict[tuple[int, float, float, int], tuple[int, ...]] = {}
        super().__init__(
            series,
            bounds=bounds,
            key=key,
            title=title,
            y_min=y_min,
            y_max=y_max,
            interactive=interactive,
        )

    @property
    def max_render_points(self) -> int | None:
        """Maximum retained samples emitted per visible series, or ``None`` for all."""

        return self._max_render_points

    @property
    def accessibility_point_limit(self) -> int:
        """Maximum point nodes exposed per series in one accessibility snapshot."""

        return self._accessibility_point_limit

    @property
    def y_domain(self) -> tuple[float, float]:
        cached = self._y_domain_cache
        if cached is not None:
            return cached

        iterator = (point.value for series in self.series for point in series.points)
        first = next(iterator)
        low = high = first
        for value in iterator:
            if value < low:
                low = value
            if value > high:
                high = value
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
        self._y_domain_cache = (low, high)
        return self._y_domain_cache

    def set_series(self, series: Sequence[ChartSeries]) -> None:
        # The parent queries the replacement viewport while publishing change
        # events, so invalidate cached domain/projection before delegating.
        self._y_domain_cache = None
        self._render_index_cache.clear()
        super().set_series(series)

    def visible_index_bounds(self, series_index: int, *, overscan: int = 1) -> tuple[int, int]:
        """Return an inclusive point-index window intersecting the current viewport."""

        if not 0 <= series_index < len(self.series):
            raise IndexError("series_index is outside the chart series range.")
        if overscan < 0:
            raise ValueError("overscan must be non-negative.")
        count = len(self.series[series_index].points)
        viewport = self.viewport
        start = max(0, math.floor(viewport.x_min) - overscan)
        end = min(count - 1, math.ceil(viewport.x_max) + overscan)
        if end < start:
            anchor = min(count - 1, max(0, round(viewport.x_min)))
            return anchor, anchor
        return start, end

    def render_indices(self, series_index: int) -> tuple[int, ...]:
        """Return deterministic, shape-preserving indices for retained rendering."""

        start, end = self.visible_index_bounds(series_index)
        count = end - start + 1
        budget = self.max_render_points
        if budget is None or count <= budget:
            return tuple(range(start, end + 1))

        viewport = self.viewport
        cache_key = (series_index, viewport.x_min, viewport.x_max, budget)
        cached = self._render_index_cache.get(cache_key)
        if cached is not None:
            return cached

        points = self.series[series_index].points
        sampled = _extrema_sample_indices(points, start, end, budget)
        if len(self._render_index_cache) >= 32:
            self._render_index_cache.clear()
        self._render_index_cache[cache_key] = sampled
        return sampled

    def visible_label_indices(self, series_index: int, *, max_labels: int = 8) -> tuple[int, ...]:
        """Pick a bounded set of visible category labels without scanning all points."""

        if max_labels <= 0:
            return ()
        start, end = self.visible_index_bounds(series_index, overscan=0)
        return _evenly_spaced_indices(start, end, max_labels)

    def accessibility_indices(self, series_index: int) -> tuple[int, ...]:
        """Return a bounded representative accessibility projection for one series."""

        if not 0 <= series_index < len(self.series):
            raise IndexError("series_index is outside the chart series range.")
        count = len(self.series[series_index].points)
        limit = self.accessibility_point_limit
        if count <= limit:
            return tuple(range(count))

        indices = list(_evenly_spaced_indices(0, count - 1, limit))
        selected = self.selection
        if selected is not None and selected.series_index == series_index:
            target = selected.point_index
            if target not in indices:
                replace_at = min(
                    range(1, len(indices) - 1),
                    key=lambda index: abs(indices[index] - target),
                )
                indices[replace_at] = target
                indices.sort()
        return tuple(indices)

    def add_category_labels(self, root: SceneNode, plot: Rect) -> None:
        points = self.series[0].points
        for index in self.visible_label_indices(0):
            point = points[index]
            x = self.x_position(index, len(points), plot)
            root.add(
                text_node(
                    f"{self.key}:x:{index}",
                    Rect(x - 38.0, plot.bottom + 7.0, 76.0, 15.0),
                    point.label,
                    10.0,
                )
            )

    def select_nearest(
        self,
        x: float,
        y: float,
        *,
        max_distance: float = 28.0,
        input_event: Event | None = None,
    ) -> ChartSelection | None:
        """Select near the pointer using an x-local candidate window.

        Cartesian points are index-spaced, so pointer proximity does not require
        an O(N) scan of every visible sample.
        """

        x = float(x)
        y = float(y)
        max_distance = float(max_distance)
        if not all(math.isfinite(value) for value in (x, y, max_distance)):
            raise ValueError("x, y and max_distance must be finite.")
        if max_distance < 0.0:
            raise ValueError("max_distance must be non-negative.")
        plot = self.plot_bounds
        if not _rect_contains(plot, x, y):
            self.clear_selection(input_event=input_event)
            return None

        viewport = self.viewport
        span = viewport.x_max - viewport.x_min
        if plot.width <= EPSILON or span <= EPSILON:
            center_index = round(viewport.x_min)
            radius = 1
        else:
            center_index = round(viewport.x_min + (x - plot.x) * span / plot.width)
            radius = max(2, math.ceil(max_distance * span / plot.width) + 1)

        low, high = viewport.y_min, viewport.y_max
        nearest: tuple[float, int, int] | None = None
        for series_index, series in enumerate(self.series):
            visible_start, visible_end = self.visible_index_bounds(series_index, overscan=0)
            start = max(visible_start, center_index - radius)
            end = min(visible_end, center_index + radius)
            for point_index in range(start, end + 1):
                position = self.point_position(series_index, point_index, plot, low, high)
                distance = math.hypot(position.x - x, position.y - y)
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, series_index, point_index)
        if nearest is None or nearest[0] > max_distance:
            self.clear_selection(input_event=input_event)
            return None
        return self.select(nearest[1], nearest[2], input_event=input_event)

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        effective_focus = self._focused or focused is self
        selected = self.selection
        total_points = sum(len(series.points) for series in self.series)
        accessibility_truncated = any(
            len(series.points) > self.accessibility_point_limit for series in self.series
        )
        series_nodes: list[AccessibilityNode] = []
        for series_index, series in enumerate(self.series):
            indices = self.accessibility_indices(series_index)
            truncated = len(indices) < len(series.points)
            description = f"{self.chart_kind} chart series"
            if truncated:
                description += f"; {len(series.points)} points, {len(indices)} representative nodes"
            children = tuple(
                AccessibilityNode(
                    key=f"{self.key}:series:{series_index}:point:{point_index}",
                    role=AccessibilityRole.LIST_ITEM,
                    name=series.points[point_index].label,
                    description=series.name,
                    enabled=self.enabled,
                    focusable=False,
                    focused=False,
                    value=series.points[point_index].value,
                    value_text=format_value(series.points[point_index].value),
                    selected=(
                        selected is not None
                        and selected.series_index == series_index
                        and selected.point_index == point_index
                    ),
                )
                for point_index in indices
            )
            series_nodes.append(
                AccessibilityNode(
                    key=f"{self.key}:series:{series_index}",
                    role=AccessibilityRole.LIST,
                    name=series.name,
                    description=description,
                    enabled=self.enabled,
                    focusable=False,
                    focused=False,
                    children=children,
                )
            )

        value_text = f"{len(self.series)} series"
        if accessibility_truncated:
            value_text += f"; {total_points} data points"
        if selected is not None:
            value_text += f"; selected {selected.label} {format_value(selected.value)}"
        if self.zoom_level > 1.0 + EPSILON:
            value_text += f"; zoom {self.zoom_level:.2f}x"
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=effective_focus,
            value_text=value_text,
            children=tuple(series_nodes),
        )


def _sample_budget(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer or None.")
    if value < _MIN_SAMPLE_BUDGET:
        raise ValueError(f"{name} must be at least {_MIN_SAMPLE_BUDGET}.")
    return value


def _extrema_sample_indices(
    points: Sequence[ChartPoint],
    start: int,
    end: int,
    budget: int,
) -> tuple[int, ...]:
    """Preserve local minima/maxima while bounding retained scene fan-out."""

    if end - start + 1 <= budget:
        return tuple(range(start, end + 1))
    if budget < _MIN_SAMPLE_BUDGET:
        raise ValueError("budget is below the supported sampling minimum.")

    bucket_count = max(1, (budget - 2) // 2)
    interior_start = start + 1
    interior_end = end
    interior_count = max(0, interior_end - interior_start)
    sampled: list[int] = [start]
    for bucket in range(bucket_count):
        left = interior_start + interior_count * bucket // bucket_count
        right = interior_start + interior_count * (bucket + 1) // bucket_count
        if left >= right:
            continue
        min_index = max_index = left
        min_value = max_value = points[left].value
        for index in range(left + 1, right):
            value = points[index].value
            if value < min_value:
                min_index, min_value = index, value
            if value > max_value:
                max_index, max_value = index, value
        if min_index == max_index:
            sampled.append(min_index)
        elif min_index < max_index:
            sampled.extend((min_index, max_index))
        else:
            sampled.extend((max_index, min_index))
    sampled.append(end)
    # Bucket arithmetic guarantees <= budget, but de-duplicate at boundaries.
    return tuple(dict.fromkeys(sampled))


def _evenly_spaced_indices(start: int, end: int, limit: int) -> tuple[int, ...]:
    if end < start or limit <= 0:
        return ()
    count = end - start + 1
    if count <= limit:
        return tuple(range(start, end + 1))
    if limit == 1:
        return (start,)
    return tuple(
        start + round(index * (count - 1) / (limit - 1))
        for index in range(limit)
    )


def _rect_contains(rect: Rect, x: float, y: float) -> bool:
    return rect.x <= x <= rect.right and rect.y <= y <= rect.bottom


__all__ = ["LargeDatasetCartesianChart"]
