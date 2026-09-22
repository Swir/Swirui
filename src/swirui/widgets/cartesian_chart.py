"""Shared retained foundation for interactive cartesian charts."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence

from swirui.core import AccessibilityNode, AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Color, CornerRadius, Point, Rect, SceneNode, SceneNodeKind

from .base import Widget
from .charts import ChartSelection, ChartSeries, ChartViewport

PALETTE = tuple(
    Color.from_hex(value)
    for value in ("#38BDF8", "#818CF8", "#34D399", "#F59E0B", "#F472B6", "#A78BFA")
)
BACKGROUND = Color.from_hex("#0B1220")
GRID = Color.from_hex("#243044")
TEXT = Color.from_hex("#CBD5E1")
SELECTION = Color.from_hex("#F8FAFC")
FOCUS = Color.from_hex("#38BDF8")
EPSILON = 1.0e-9

_VK_ESCAPE = 0x1B
_VK_0 = 0x30
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_NUMPAD_ADD = 0x6B
_VK_NUMPAD_SUBTRACT = 0x6D
_VK_OEM_PLUS = 0xBB
_VK_OEM_MINUS = 0xBD
_ZOOM_STEP = 1.25
_MIN_Y_ZOOM_FRACTION = 0.02
_MIN_HIT_DISTANCE = 28.0


class CartesianChart(Widget):
    """Axes, scaling, selection and zoom shared by retained cartesian charts."""

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
        interactive: bool = True,
    ) -> None:
        normalized_title = title.strip() if title is not None else None
        if normalized_title == "":
            raise ValueError("Chart title must not be empty.")
        self._series = self._validate_series(series)
        self._title = normalized_title
        self._y_min = _finite_optional(y_min, "y_min")
        self._y_max = _finite_optional(y_max, "y_max")
        if self._y_min is not None and self._y_max is not None and self._y_min >= self._y_max:
            raise ValueError("y_min must be smaller than y_max.")
        self._interactive = bool(interactive)
        self._viewport: ChartViewport | None = None
        self._selection: ChartSelection | None = None
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            clip_to_bounds=True,
            focusable=self._interactive,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=normalized_title or self.__class__.__name__,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_scroll", self._on_pointer_scroll)
        self.on("key_down", self._on_key_down)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)

    @property
    def series(self) -> tuple[ChartSeries, ...]:
        return self._series

    @property
    def interactive(self) -> bool:
        return self._interactive

    @property
    def selection(self) -> ChartSelection | None:
        return self._selection

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
    def viewport(self) -> ChartViewport:
        if self._viewport is not None:
            return self._viewport
        x_min, x_max = self._full_x_domain()
        y_min, y_max = self.y_domain
        return ChartViewport(x_min, x_max, y_min, y_max)

    @property
    def zoom_level(self) -> float:
        full = self._full_viewport()
        current = self.viewport
        x_full = full.x_max - full.x_min
        x_current = current.x_max - current.x_min
        x_zoom = x_full / x_current if x_full > EPSILON and x_current > EPSILON else 1.0
        y_zoom = (full.y_max - full.y_min) / (current.y_max - current.y_min)
        return max(1.0, x_zoom, y_zoom)

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
        if normalized == self._series:
            return
        had_selection = self._selection
        old_viewport = self.viewport
        self._series = normalized
        self._selection = None
        self._viewport = None
        self.invalidate(reason="chart_series")
        if had_selection is not None:
            self.emit(
                "selection_changed",
                old_selection=had_selection,
                selection=None,
                input_event=None,
            )
        if old_viewport != self.viewport:
            self.emit(
                "zoom_changed",
                old_viewport=old_viewport,
                viewport=self.viewport,
                input_event=None,
            )

    def select(
        self,
        series_index: int,
        point_index: int,
        *,
        input_event: Event | None = None,
    ) -> ChartSelection:
        if not 0 <= series_index < len(self.series):
            raise IndexError("series_index is outside the chart series range.")
        series = self.series[series_index]
        if not 0 <= point_index < len(series.points):
            raise IndexError("point_index is outside the selected series range.")
        point = series.points[point_index]
        selection = ChartSelection(
            series.key,
            point.key,
            series_index,
            point_index,
            point.label,
            point.value,
        )
        self._set_selection(selection, input_event=input_event)
        return selection

    def select_by_key(
        self,
        series_key: Hashable,
        point_key: Hashable,
        *,
        input_event: Event | None = None,
    ) -> ChartSelection:
        for series_index, series in enumerate(self.series):
            if series.key != series_key:
                continue
            for point_index, point in enumerate(series.points):
                if point.key == point_key:
                    return self.select(series_index, point_index, input_event=input_event)
            raise KeyError(f"Unknown point key {point_key!r} in chart series {series_key!r}.")
        raise KeyError(f"Unknown chart series key {series_key!r}.")

    def clear_selection(self, *, input_event: Event | None = None) -> None:
        self._set_selection(None, input_event=input_event)

    def select_nearest(
        self,
        x: float,
        y: float,
        *,
        max_distance: float = _MIN_HIT_DISTANCE,
        input_event: Event | None = None,
    ) -> ChartSelection | None:
        x = _finite(x, "x")
        y = _finite(y, "y")
        max_distance = _finite(max_distance, "max_distance")
        if max_distance < 0.0:
            raise ValueError("max_distance must be non-negative.")
        plot = self.plot_bounds
        if not _rect_contains(plot, x, y):
            self.clear_selection(input_event=input_event)
            return None
        low, high = self.viewport.y_min, self.viewport.y_max
        nearest: tuple[float, int, int] | None = None
        for series_index, series in enumerate(self.series):
            for point_index, _point in enumerate(series.points):
                if not self.index_visible(point_index):
                    continue
                position = self.point_position(series_index, point_index, plot, low, high)
                distance = math.hypot(position.x - x, position.y - y)
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, series_index, point_index)
        if nearest is None or nearest[0] > max_distance:
            self.clear_selection(input_event=input_event)
            return None
        return self.select(nearest[1], nearest[2], input_event=input_event)

    def zoom(
        self,
        factor: float,
        *,
        anchor_x: float = 0.5,
        anchor_y: float = 0.5,
        input_event: Event | None = None,
    ) -> ChartViewport:
        factor = _finite(factor, "factor")
        anchor_x = _unit_interval(anchor_x, "anchor_x")
        anchor_y = _unit_interval(anchor_y, "anchor_y")
        if factor <= 0.0:
            raise ValueError("factor must be greater than zero.")
        if math.isclose(factor, 1.0, abs_tol=EPSILON):
            return self.viewport

        full = self._full_viewport()
        current = self.viewport

        full_x_span = full.x_max - full.x_min
        current_x_span = current.x_max - current.x_min
        if full_x_span <= EPSILON:
            x_min, x_max = full.x_min, full.x_max
        else:
            min_x_span = min(full_x_span, 1.0)
            new_x_span = max(min_x_span, min(full_x_span, current_x_span / factor))
            x_anchor_value = current.x_min + current_x_span * anchor_x
            x_min = x_anchor_value - new_x_span * anchor_x
            x_min = _clamp_window_start(x_min, new_x_span, full.x_min, full.x_max)
            x_max = x_min + new_x_span

        full_y_span = full.y_max - full.y_min
        current_y_span = current.y_max - current.y_min
        min_y_span = max(full_y_span * _MIN_Y_ZOOM_FRACTION, EPSILON * 10.0)
        new_y_span = max(min_y_span, min(full_y_span, current_y_span / factor))
        y_anchor_value = current.y_min + current_y_span * anchor_y
        y_min = y_anchor_value - new_y_span * anchor_y
        y_min = _clamp_window_start(y_min, new_y_span, full.y_min, full.y_max)
        y_max = y_min + new_y_span

        viewport = ChartViewport(x_min, x_max, y_min, y_max)
        self._set_viewport(viewport, input_event=input_event)
        return self.viewport

    def reset_zoom(self, *, input_event: Event | None = None) -> None:
        if self._viewport is None:
            return
        old_viewport = self._viewport
        self._viewport = None
        self.invalidate(reason="chart_viewport")
        self.emit(
            "zoom_changed",
            old_viewport=old_viewport,
            viewport=self.viewport,
            input_event=input_event,
        )

    def build_scene_node(self) -> SceneNode:
        root = rectangle_node(
            self.key,
            self.bounds,
            BACKGROUND,
            radius=8.0,
            clip_to_bounds=True,
            hit_testable=self.enabled and self.interactive,
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
        viewport = self.viewport
        self._add_axes(root, plot, viewport.y_min, viewport.y_max)
        self.add_category_labels(root, plot)
        data_layer = SceneNode(
            key=f"{self.key}:plot",
            kind=SceneNodeKind.GROUP,
            bounds=plot,
            clip_to_bounds=True,
            hit_testable=False,
        )
        self.add_data_nodes(data_layer, plot, viewport.y_min, viewport.y_max)
        self._add_selection_node(data_layer, plot, viewport.y_min, viewport.y_max)
        root.add(data_layer)
        if self._focused and self.enabled:
            self._add_focus_outline(root)
        return root

    def accessibility_snapshot(self, *, focused: object | None = None) -> AccessibilityNode:
        effective_focus = self._focused or focused is self
        selected = self.selection
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
                        selected=(
                            selected is not None
                            and selected.series_index == series_index
                            and selected.point_index == point_index
                        ),
                    )
                    for point_index, point in enumerate(series.points)
                ),
            )
            for series_index, series in enumerate(self.series)
        )
        value_text = f"{len(self.series)} series"
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
            children=series_nodes,
        )

    def add_category_labels(self, root: SceneNode, plot: Rect) -> None:
        points = self.series[0].points
        stride = max(1, math.ceil(len(points) / 8))
        for index, point in enumerate(points):
            if not self.index_visible(index):
                continue
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

    def x_position(self, index: int, count: int, plot: Rect) -> float:
        if count <= 1:
            return plot.x + plot.width / 2.0
        viewport = self.viewport
        span = viewport.x_max - viewport.x_min
        if span <= EPSILON:
            return plot.x + plot.width / 2.0
        return plot.x + (index - viewport.x_min) * plot.width / span

    @staticmethod
    def value_y(value: float, plot: Rect, low: float, high: float) -> float:
        return plot.bottom - (value - low) * plot.height / (high - low)

    def point_position(
        self,
        series_index: int,
        point_index: int,
        plot: Rect,
        low: float,
        high: float,
    ) -> Point:
        series = self.series[series_index]
        point = series.points[point_index]
        return Point(
            self.x_position(point_index, len(series.points), plot),
            self.value_y(point.value, plot, low, high),
        )

    def index_visible(self, index: int) -> bool:
        viewport = self.viewport
        return viewport.x_min - EPSILON <= index <= viewport.x_max + EPSILON

    def series_color(self, index: int) -> Color:
        series = self.series[index]
        return series.color or PALETTE[index % len(PALETTE)]

    def _full_x_domain(self) -> tuple[float, float]:
        count = max(len(series.points) for series in self.series)
        return 0.0, float(max(0, count - 1))

    def _full_viewport(self) -> ChartViewport:
        x_min, x_max = self._full_x_domain()
        y_min, y_max = self.y_domain
        return ChartViewport(x_min, x_max, y_min, y_max)

    def _set_viewport(self, viewport: ChartViewport, *, input_event: Event | None) -> None:
        full = self._full_viewport()
        x_min = max(full.x_min, viewport.x_min)
        x_max = min(full.x_max, viewport.x_max)
        if full.x_max - full.x_min <= EPSILON:
            x_min = x_max = full.x_min
        elif x_min >= x_max:
            raise ValueError("Chart viewport does not overlap the x-domain.")
        y_min = max(full.y_min, viewport.y_min)
        y_max = min(full.y_max, viewport.y_max)
        if y_min >= y_max:
            raise ValueError("Chart viewport does not overlap the y-domain.")
        normalized = ChartViewport(x_min, x_max, y_min, y_max)
        old_viewport = self.viewport
        if _viewports_close(normalized, full):
            self._viewport = None
        else:
            self._viewport = normalized
        if _viewports_close(old_viewport, self.viewport):
            return
        self.invalidate(reason="chart_viewport")
        self.emit(
            "zoom_changed",
            old_viewport=old_viewport,
            viewport=self.viewport,
            input_event=input_event,
        )

    def _set_selection(
        self,
        selection: ChartSelection | None,
        *,
        input_event: Event | None,
    ) -> None:
        if selection == self._selection:
            return
        old_selection = self._selection
        self._selection = selection
        self.invalidate(reason="chart_selection")
        self.emit(
            "selection_changed",
            old_selection=old_selection,
            selection=selection,
            input_event=input_event,
        )

    def _add_selection_node(
        self,
        root: SceneNode,
        plot: Rect,
        low: float,
        high: float,
    ) -> None:
        selected = self.selection
        if selected is None or not self.index_visible(selected.point_index):
            return
        position = self.point_position(
            selected.series_index,
            selected.point_index,
            plot,
            low,
            high,
        )
        root.add(
            rectangle_node(
                f"{self.key}:selection:halo",
                Rect(position.x - 8.0, position.y - 8.0, 16.0, 16.0),
                SELECTION.with_alpha(0.24),
                radius=8.0,
            ),
            rectangle_node(
                f"{self.key}:selection:marker",
                Rect(position.x - 4.0, position.y - 4.0, 8.0, 8.0),
                SELECTION,
                radius=4.0,
            ),
        )

    def _add_focus_outline(self, root: SceneNode) -> None:
        inset = 2.0
        left = self.bounds.x + inset
        top = self.bounds.y + inset
        width = max(0.0, self.bounds.width - inset * 2.0)
        height = max(0.0, self.bounds.height - inset * 2.0)
        if width <= 0.0 or height <= 0.0:
            return
        root.add(
            rectangle_node(f"{self.key}:focus:top", Rect(left, top, width, 1.0), FOCUS),
            rectangle_node(
                f"{self.key}:focus:bottom",
                Rect(left, top + height - 1.0, width, 1.0),
                FOCUS,
            ),
            rectangle_node(f"{self.key}:focus:left", Rect(left, top, 1.0, height), FOCUS),
            rectangle_node(
                f"{self.key}:focus:right",
                Rect(left + width - 1.0, top, 1.0, height),
                FOCUS,
            ),
        )

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

    def _on_pointer_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or not self.interactive
            or native is None
            or native.button is not PointerButton.LEFT
            or native.x is None
            or native.y is None
        ):
            return
        self.select_nearest(native.x, native.y, input_event=event)
        event.prevent_default()

    def _on_pointer_scroll(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_SCROLL)
        if not self.enabled or not self.interactive or native is None or native.delta_y == 0.0:
            return
        plot = self.plot_bounds
        anchor_x = 0.5
        anchor_y = 0.5
        if native.x is not None and plot.width > EPSILON:
            anchor_x = min(1.0, max(0.0, (native.x - plot.x) / plot.width))
        if native.y is not None and plot.height > EPSILON:
            anchor_y = min(1.0, max(0.0, (plot.bottom - native.y) / plot.height))
        factor = _ZOOM_STEP if native.delta_y < 0.0 else 1.0 / _ZOOM_STEP
        self.zoom(factor, anchor_x=anchor_x, anchor_y=anchor_y, input_event=event)
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or not self.interactive or native is None:
            return
        if native.ctrl or native.alt or native.meta:
            return
        key = native.key_code
        if key in (_VK_OEM_PLUS, _VK_NUMPAD_ADD):
            self.zoom(_ZOOM_STEP, input_event=event)
        elif key in (_VK_OEM_MINUS, _VK_NUMPAD_SUBTRACT):
            self.zoom(1.0 / _ZOOM_STEP, input_event=event)
        elif key == _VK_0:
            self.reset_zoom(input_event=event)
        elif key == _VK_ESCAPE:
            self.clear_selection(input_event=event)
        elif key == _VK_LEFT:
            self._move_selection(0, -1, input_event=event)
        elif key == _VK_RIGHT:
            self._move_selection(0, 1, input_event=event)
        elif key == _VK_UP:
            self._move_selection(-1, 0, input_event=event)
        elif key == _VK_DOWN:
            self._move_selection(1, 0, input_event=event)
        else:
            return
        event.prevent_default()

    def _move_selection(
        self,
        series_delta: int,
        point_delta: int,
        *,
        input_event: Event | None,
    ) -> None:
        if self.selection is None:
            self.select(0, 0, input_event=input_event)
            return
        series_index = min(
            len(self.series) - 1,
            max(0, self.selection.series_index + series_delta),
        )
        point_index = min(
            len(self.series[series_index].points) - 1,
            max(0, self.selection.point_index + point_delta),
        )
        self.select(series_index, point_index, input_event=input_event)

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        if self._focused:
            self._focused = False
            self.invalidate(reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._focused = False

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        native = event.data.get("event")
        if isinstance(native, PlatformEvent) and native.kind is kind:
            return native
        return None

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
    hit_testable: bool = False,
) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.RECTANGLE,
        bounds=bounds,
        fill=color,
        corner_radius=CornerRadius.uniform(radius),
        clip_to_bounds=clip_to_bounds,
        hit_testable=hit_testable,
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
    return _finite(value, name)


def _finite(value: float, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


def _unit_interval(value: float, name: str) -> float:
    normalized = _finite(value, name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0.")
    return normalized


def _clamp_window_start(start: float, span: float, full_min: float, full_max: float) -> float:
    return min(max(start, full_min), full_max - span)


def _rect_contains(rect: Rect, x: float, y: float) -> bool:
    return rect.x <= x <= rect.right and rect.y <= y <= rect.bottom


def _viewports_close(left: ChartViewport, right: ChartViewport) -> bool:
    return all(
        math.isclose(a, b, rel_tol=1.0e-9, abs_tol=1.0e-9)
        for a, b in (
            (left.x_min, right.x_min),
            (left.x_max, right.x_max),
            (left.y_min, right.y_min),
            (left.y_max, right.y_max),
        )
    )
