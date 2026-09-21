"""Retained gauge, candlestick and timeline chart implementations."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

from swirui.core import AccessibilityNode, AccessibilityRole
from swirui.rendering import Color, Point, Rect, SceneNode

from .base import Widget
from .cartesian_chart import (
    BACKGROUND,
    EPSILON,
    GRID,
    PALETTE,
    CartesianChart,
    format_value,
    rectangle_node,
    text_node,
)
from .charts import ChartPoint, ChartSeries
from .line_area_chart import polygon_node, segment_node

_GAUGE_ACTIVE = Color.from_hex("#38BDF8")
_GAUGE_INACTIVE = Color.from_hex("#263449")
_CANDLE_UP = Color.from_hex("#34D399")
_CANDLE_DOWN = Color.from_hex("#FB7185")
_CANDLE_DOJI = Color.from_hex("#F59E0B")


@dataclass(frozen=True, slots=True)
class CandlestickPoint:
    """One OHLC sample with a stable identity and display label."""

    key: Hashable
    label: str
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        hash(self.key)
        label = self.label.strip()
        values = tuple(float(value) for value in (self.open, self.high, self.low, self.close))
        if not label:
            raise ValueError("CandlestickPoint label must not be empty.")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("CandlestickPoint OHLC values must be finite.")
        open_value, high, low, close = values
        if high < max(open_value, close) or low > min(open_value, close) or high < low:
            raise ValueError("CandlestickPoint high/low must contain open and close.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "open", open_value)
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "close", close)


@dataclass(frozen=True, slots=True)
class TimelineChartItem:
    """One labelled interval rendered on a timeline chart lane."""

    key: Hashable
    label: str
    start: float
    end: float
    color: Color | None = None

    def __post_init__(self) -> None:
        hash(self.key)
        label = self.label.strip()
        start = float(self.start)
        end = float(self.end)
        if not label:
            raise ValueError("TimelineChartItem label must not be empty.")
        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError("TimelineChartItem bounds must be finite.")
        if end <= start:
            raise ValueError("TimelineChartItem end must be greater than start.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


class GaugeChart(Widget):
    """Retained 270-degree gauge with deterministic segment geometry."""

    def __init__(
        self,
        value: float,
        *,
        bounds: Rect,
        minimum: float = 0.0,
        maximum: float = 100.0,
        key: str | None = None,
        title: str | None = None,
        segments: int = 48,
    ) -> None:
        normalized_title = _title(title)
        minimum = _finite(minimum, "minimum")
        maximum = _finite(maximum, "maximum")
        if maximum <= minimum:
            raise ValueError("maximum must be greater than minimum.")
        if not 12 <= int(segments) <= 128:
            raise ValueError("segments must be between 12 and 128.")
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.PROGRESS_BAR,
            accessible_name=normalized_title or "Gauge chart",
        )
        self._minimum = minimum
        self._maximum = maximum
        self._segments = int(segments)
        self._title = normalized_title
        self._value = self._normalize_value(value)
        self._sync_accessibility()

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        normalized = self._normalize_value(value)
        if normalized == self._value:
            return
        self._value = normalized
        self._sync_accessibility()
        self.invalidate(reason="gauge_value")
        self.emit("changed", value=normalized)

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def maximum(self) -> float:
        return self._maximum

    @property
    def progress(self) -> float:
        return (self.value - self.minimum) / (self.maximum - self.minimum)

    def build_scene_node(self) -> SceneNode:
        root = _chart_root(self.key, self.bounds, self._title)
        top = self.bounds.y + (38.0 if self._title else 14.0)
        available_height = max(0.0, self.bounds.bottom - top - 18.0)
        radius = max(0.0, min(self.bounds.width - 32.0, available_height) / 2.0)
        if radius <= 0.0:
            return root
        center = Point(self.bounds.x + self.bounds.width / 2.0, top + available_height / 2.0 + 8.0)
        thickness = max(5.0, min(18.0, radius * 0.17))
        inner = max(0.0, radius - thickness)
        start = math.radians(135.0)
        sweep = math.radians(270.0)
        active = round(self._segments * self.progress)
        gap = min(math.radians(1.2), sweep / self._segments * 0.18)

        for index in range(self._segments):
            a0 = start + sweep * index / self._segments + gap / 2.0
            a1 = start + sweep * (index + 1) / self._segments - gap / 2.0
            points = (
                Point(center.x + math.cos(a0) * radius, center.y + math.sin(a0) * radius),
                Point(center.x + math.cos(a1) * radius, center.y + math.sin(a1) * radius),
                Point(center.x + math.cos(a1) * inner, center.y + math.sin(a1) * inner),
                Point(center.x + math.cos(a0) * inner, center.y + math.sin(a0) * inner),
            )
            node = polygon_node(
                f"{self.key}:segment:{index}",
                points,
                _GAUGE_ACTIVE if index < active else _GAUGE_INACTIVE,
            )
            if node is not None:
                root.add(node)

        root.add(
            text_node(
                f"{self.key}:value",
                Rect(center.x - radius * 0.52, center.y - 15.0, radius * 1.04, 30.0),
                format_value(self.value),
                max(16.0, min(28.0, radius * 0.24)),
            )
        )
        root.add(
            text_node(
                f"{self.key}:minimum",
                Rect(center.x - radius, center.y + radius * 0.48, radius * 0.5, 14.0),
                format_value(self.minimum),
                10.0,
            )
        )
        root.add(
            text_node(
                f"{self.key}:maximum",
                Rect(center.x + radius * 0.5, center.y + radius * 0.48, radius * 0.5, 14.0),
                format_value(self.maximum),
                10.0,
            )
        )
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.PROGRESS_BAR,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=False,
            focused=False,
            value=self.value,
            min_value=self.minimum,
            max_value=self.maximum,
            value_text=format_value(self.value),
        )

    def _normalize_value(self, value: float) -> float:
        normalized = _finite(value, "value")
        return max(self.minimum, min(self.maximum, normalized))

    def _sync_accessibility(self) -> None:
        self.accessible_value = self.value
        self.accessible_min_value = self.minimum
        self.accessible_max_value = self.maximum
        self.accessible_value_text = format_value(self.value)


class CandlestickChart(CartesianChart):
    """Retained OHLC candlestick chart sharing the verified cartesian axis path."""

    chart_kind = "candlestick"

    def __init__(
        self,
        points: Sequence[CandlestickPoint],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> None:
        normalized = _validate_candles(points)
        self._points = normalized
        synthetic = ChartSeries(
            "candles",
            "Candles",
            tuple(ChartPoint(point.key, point.label, point.close) for point in normalized),
        )
        super().__init__(
            (synthetic,),
            bounds=bounds,
            key=key,
            title=title,
            y_min=y_min,
            y_max=y_max,
        )

    @property
    def points(self) -> tuple[CandlestickPoint, ...]:
        return self._points

    @property
    def y_domain(self) -> tuple[float, float]:
        low = min(point.low for point in self.points)
        high = max(point.high for point in self.points)
        if self._y_min is not None:
            low = self._y_min
        if self._y_max is not None:
            high = self._y_max
        if low > high:
            raise ValueError("Configured candlestick y-domain is invalid.")
        if math.isclose(low, high, abs_tol=EPSILON):
            padding = max(1.0, abs(low) * 0.1)
            low, high = low - padding, high + padding
        return low, high

    def set_points(self, points: Sequence[CandlestickPoint]) -> None:
        normalized = _validate_candles(points)
        if normalized == self._points:
            return
        self._points = normalized
        self._series = (
            ChartSeries(
                "candles",
                "Candles",
                tuple(ChartPoint(point.key, point.label, point.close) for point in normalized),
            ),
        )
        self.invalidate(reason="candlestick_points")

    def add_data_nodes(self, root: SceneNode, plot: Rect, low: float, high: float) -> None:
        count = len(self.points)
        spacing = plot.width if count == 1 else plot.width / max(1, count - 1)
        body_width = max(3.0, min(22.0, spacing * 0.48))
        for index, point in enumerate(self.points):
            x = self.x_position(index, count, plot)
            high_y = self.value_y(point.high, plot, low, high)
            low_y = self.value_y(point.low, plot, low, high)
            open_y = self.value_y(point.open, plot, low, high)
            close_y = self.value_y(point.close, plot, low, high)
            rising = point.close > point.open
            falling = point.close < point.open
            color = _CANDLE_UP if rising else _CANDLE_DOWN if falling else _CANDLE_DOJI

            wick = segment_node(
                f"{self.key}:candle:{index}:wick",
                Point(x, high_y),
                Point(x, low_y),
                color,
            )
            if wick is not None:
                root.add(wick)

            top = min(open_y, close_y)
            height = max(2.0, abs(close_y - open_y))
            root.add(
                rectangle_node(
                    f"{self.key}:candle:{index}:body",
                    Rect(x - body_width / 2.0, top, body_width, height),
                    color,
                    radius=min(2.5, body_width * 0.15),
                )
            )

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:candle:{index}",
                role=AccessibilityRole.LIST_ITEM,
                name=point.label,
                description="candlestick OHLC sample",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                value=point.close,
                value_text=(
                    f"open {format_value(point.open)}, high {format_value(point.high)}, "
                    f"low {format_value(point.low)}, close {format_value(point.close)}"
                ),
            )
            for index, point in enumerate(self.points)
        )
        return _group_snapshot(self, f"{len(self.points)} candles", children)


class TimelineChart(Widget):
    """Retained horizontal interval chart with independent labelled lanes."""

    def __init__(
        self,
        items: Sequence[TimelineChartItem],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
    ) -> None:
        normalized_title = _title(title)
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or "Timeline chart",
        )
        self._items = _validate_timeline_items(items)
        self._title = normalized_title

    @property
    def items(self) -> tuple[TimelineChartItem, ...]:
        return self._items

    @property
    def domain(self) -> tuple[float, float]:
        return (
            min(item.start for item in self.items),
            max(item.end for item in self.items),
        )

    @property
    def plot_bounds(self) -> Rect:
        top = self.bounds.y + (38.0 if self._title else 16.0)
        return Rect(
            self.bounds.x + 112.0,
            top,
            max(0.0, self.bounds.width - 128.0),
            max(0.0, self.bounds.bottom - top - 34.0),
        )

    def set_items(self, items: Sequence[TimelineChartItem]) -> None:
        normalized = _validate_timeline_items(items)
        if normalized != self._items:
            self._items = normalized
            self.invalidate(reason="timeline_chart_items")

    def build_scene_node(self) -> SceneNode:
        root = _chart_root(self.key, self.bounds, self._title)
        plot = self.plot_bounds
        if plot.width <= 0.0 or plot.height <= 0.0:
            return root
        low, high = self.domain
        span = high - low
        for index in range(5):
            fraction = index / 4.0
            x = plot.x + fraction * plot.width
            root.add(
                rectangle_node(
                    f"{self.key}:grid:{index}",
                    Rect(x, plot.y, 1.0, plot.height),
                    GRID,
                )
            )
            root.add(
                text_node(
                    f"{self.key}:tick:{index}",
                    Rect(x - 28.0, plot.bottom + 7.0, 56.0, 14.0),
                    format_value(low + fraction * span),
                    10.0,
                )
            )

        lane_height = plot.height / len(self.items)
        for index, item in enumerate(self.items):
            y = plot.y + index * lane_height
            color = item.color or PALETTE[index % len(PALETTE)]
            start_x = plot.x + (item.start - low) * plot.width / span
            end_x = plot.x + (item.end - low) * plot.width / span
            bar_height = max(4.0, min(24.0, lane_height * 0.54))
            bar_y = y + max(0.0, (lane_height - bar_height) / 2.0)
            if lane_height >= 14.0:
                root.add(
                    text_node(
                        f"{self.key}:label:{index}",
                        Rect(
                            self.bounds.x + 8.0,
                            y + max(0.0, lane_height / 2.0 - 7.0),
                            96.0,
                            14.0,
                        ),
                        item.label,
                        10.0,
                    )
                )
            root.add(
                rectangle_node(
                    f"{self.key}:item:{index}:bar",
                    Rect(start_x, bar_y, max(1.0, end_x - start_x), bar_height),
                    color,
                    radius=min(6.0, bar_height / 2.0),
                )
            )
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        del focused
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:item:{index}",
                role=AccessibilityRole.LIST_ITEM,
                name=item.label,
                description="timeline interval",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                value=item.end - item.start,
                value_text=f"{format_value(item.start)} to {format_value(item.end)}",
            )
            for index, item in enumerate(self.items)
        )
        return _group_snapshot(self, f"{len(self.items)} intervals", children)


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


def _validate_candles(points: Sequence[CandlestickPoint]) -> tuple[CandlestickPoint, ...]:
    normalized = tuple(points)
    if not normalized:
        raise ValueError("CandlestickChart requires at least one point.")
    _validate_unique_keys((point.key for point in normalized), "candlestick")
    return normalized


def _validate_timeline_items(items: Sequence[TimelineChartItem]) -> tuple[TimelineChartItem, ...]:
    normalized = tuple(items)
    if not normalized:
        raise ValueError("TimelineChart requires at least one item.")
    _validate_unique_keys((item.key for item in normalized), "timeline item")
    return normalized


def _validate_unique_keys(keys: Iterable[Hashable], kind: str) -> None:
    seen: set[Hashable] = set()
    for key in keys:
        if key in seen:
            raise ValueError(f"Duplicate {kind} key: {key!r}")
        seen.add(key)


def _title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("Chart title must not be empty.")
    return normalized


def _finite(value: float, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized
