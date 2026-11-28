"""Retained progress widgets."""

from __future__ import annotations

import math
from collections.abc import Sequence
from functools import lru_cache
from itertools import pairwise

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Color, CornerRadius, Path2D, Point, Rect, Size, _signed_area
from swirui.rendering.gradients import (
    GradientStop,
    LinearGradient,
    _color_at_stops,
    _validate_stops,
)
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import Theme

from .base import Widget, _gradient_track_fill

_TRACK = Color.from_hex("#263946")
_FILL = Color.from_hex("#0A98F0")
_DISABLED = Color.from_hex("#46545D")


def _validate_range(minimum: float, maximum: float) -> tuple[float, float]:
    minimum = float(minimum)
    maximum = float(maximum)
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        raise ValueError("minimum and maximum must be finite.")
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum.")
    return minimum, maximum


def _clamp(value: float, minimum: float, maximum: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError("value must be finite.")
    return max(minimum, min(maximum, normalized))


def _format_percent(progress: float) -> str:
    return f"{progress * 100.0:.0f}%"


class _ProgressWidget(Widget):
    """Shared bounded progress state and accessibility semantics."""

    _track: Color
    _fill: Color
    _disabled: Color

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float,
        minimum: float,
        maximum: float,
        key: str | None,
        theme: Theme | None,
        opacity: float,
        z_index: int,
        accessible_name: str | None,
        accessible_description: str | None,
    ) -> None:
        self._minimum, self._maximum = _validate_range(minimum, maximum)
        self._value = _clamp(value, self._minimum, self._maximum)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=False,
            accessibility_role=AccessibilityRole.PROGRESS_BAR,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._bind_theme(
            theme,
            {
                "_track": ("surface", "border", _TRACK),
                "_fill": ("surface", "accent", _FILL),
                "_disabled": ("surface", "disabled", _DISABLED),
            },
            {},
        )
        self._sync_accessibility()

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def maximum(self) -> float:
        return self._maximum

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        normalized = _clamp(value, self._minimum, self._maximum)
        if normalized == self._value:
            return
        old_value = self._value
        self._value = normalized
        self._sync_accessibility()
        self.invalidate(reason="value")
        self.emit("changed", old_value=old_value, value=normalized)

    @property
    def progress(self) -> float:
        return (self._value - self._minimum) / (self._maximum - self._minimum)

    def _sync_accessibility(self) -> None:
        self.accessible_value = self._value
        self.accessible_min_value = self._minimum
        self.accessible_max_value = self._maximum
        self.accessible_value_text = _format_percent(self.progress)


class ProgressBar(_ProgressWidget):
    """Determinate bar with an optional gradient anchored to the entire track."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        fill_gradient: LinearGradient | None = None,
        key: str | None = None,
        theme: Theme | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            theme=theme,
            value=value,
            minimum=minimum,
            maximum=maximum,
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._fill_gradient: LinearGradient | None = None
        self.fill_gradient = fill_gradient

    @property
    def fill_gradient(self) -> LinearGradient | None:
        """The track-wide color scale. None uses the current theme accent."""
        return self._fill_gradient

    @fill_gradient.setter
    def fill_gradient(self, value: LinearGradient | None) -> None:
        if value is not None and not isinstance(value, LinearGradient):
            raise TypeError("fill_gradient must be a LinearGradient or None.")
        if value != self._fill_gradient:
            self._fill_gradient = value
            self.invalidate(reason="fill_gradient")

    def build_scene_node(self) -> SceneNode:
        radius = min(self.bounds.height / 2.0, self.bounds.width / 2.0)
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._track if self.enabled else self._disabled,
            corner_radius=CornerRadius.uniform(radius),
            hit_testable=False,
        )
        fill_width = self.bounds.width * self.progress
        if fill_width <= 0.0 or self.bounds.height <= 0.0:
            return root
        key = f"{self.key}:fill"
        filled = Rect(self.bounds.x, self.bounds.y, fill_width, self.bounds.height)
        if self.enabled and self.fill_gradient is not None:
            paint = _gradient_track_fill(
                self.fill_gradient, key, self.bounds, filled, root.corner_radius
            )
        else:
            paint = SceneNode(
                key, SceneNodeKind.RECTANGLE, filled, z_index=1,
                fill=self._fill if self.enabled else self._disabled,
                corner_radius=CornerRadius.uniform(min(radius, fill_width / 2.0)),
                hit_testable=False,
            )
        root.add(paint)
        return root


class ProgressRing(_ProgressWidget):
    """Clockwise progress ring with an optional fixed color scale starting at twelve o'clock."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        thickness: float = 6.0,
        segments: int = 48,
        sweep_stops: Sequence[GradientStop] | None = None,
        key: str | None = None,
        theme: Theme | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        thickness = float(thickness)
        if not math.isfinite(thickness) or thickness <= 0.0:
            raise ValueError("thickness must be finite and greater than zero.")
        if not 8 <= int(segments) <= 128:
            raise ValueError("segments must be between 8 and 128.")
        self._thickness = thickness
        self._segments = int(segments)
        self._sweep_stops: tuple[GradientStop, ...] | None = None
        self._sweep_colors: tuple[Color, ...] = ()
        super().__init__(
            bounds=bounds,
            theme=theme,
            value=value,
            minimum=minimum,
            maximum=maximum,
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.sweep_stops = sweep_stops

    @property
    def thickness(self) -> float:
        return self._thickness

    @property
    def segments(self) -> int:
        return self._segments

    @property
    def sweep_stops(self) -> tuple[GradientStop, ...] | None:
        """Colors along one full turn. None follows the current theme accent."""
        return self._sweep_stops

    @sweep_stops.setter
    def sweep_stops(self, value: Sequence[GradientStop] | None) -> None:
        stops = None if value is None else tuple(value)
        if stops == self._sweep_stops:
            return
        colors: tuple[Color, ...] = ()
        if stops is not None:
            if not all(isinstance(stop, GradientStop) for stop in stops):
                raise TypeError("sweep_stops must contain GradientStop values.")
            _validate_stops(stops)
            colors = tuple(_color_at_stops(stops, (index + .5) / self.segments)
                           for index in range(self.segments))
        self._sweep_stops = stops
        self._sweep_colors = colors
        self.invalidate(reason="sweep_stops")

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            hit_testable=False,
        )
        sweep = self.progress * self.segments
        step_angle = math.tau / self.segments

        def paint(key: str, path: Path2D | None, color: Color) -> None:
            if path is not None:
                root.children.append(SceneNode(
                    key, SceneNodeKind.PATH, self.bounds, fill=color, path=path,
                    z_index=1, hit_testable=False,
                ))

        track = _ring_track(self.bounds.size, self.thickness, self.segments)
        for index, segment in enumerate(track):
            key = f"{self.key}:segment:{index}"
            fraction = sweep - index
            fill = self._sweep_colors[index] if self._sweep_colors else self._fill
            if segment is not None and self.enabled and 0 < fraction < 1:
                # Intersect the progress ray with both polygon edges. Splitting the
                # chords keeps the outline fixed even on deliberately faceted rings.
                leading = math.sin(fraction * step_angle)
                weight = leading / (leading + math.sin((1 - fraction) * step_angle))
                outer_a, outer_b, inner_b = segment.points[:3]
                inner_a = segment.points[-1]
                outer_tip = Point(outer_a.x + weight * (outer_b.x - outer_a.x),
                                  outer_a.y + weight * (outer_b.y - outer_a.y))
                inner_tip = Point(inner_a.x + weight * (inner_b.x - inner_a.x),
                                  inner_a.y + weight * (inner_b.y - inner_a.y))
                paint(key, _ring_wedge(outer_a, outer_tip, inner_tip, inner_a), fill)
                remaining = _ring_wedge(outer_tip, outer_b, inner_b, inner_tip)
                paint(key + ":remaining", remaining, self._track)
            else:
                color = fill if fraction >= 1 else self._track
                paint(key, segment, color if self.enabled else self._disabled)
        return root


def _ring_wedge(a: Point, b: Point, inner_b: Point, inner_a: Point) -> Path2D | None:
    points = (a, b, inner_b, inner_a)
    if abs(_signed_area(points)) <= 1e-9:
        return None
    return Path2D._from_convex_outline(points)


@lru_cache(maxsize=32)
def _ring_track(size: Size, thickness: float, segments: int) -> tuple[Path2D | None, ...]:
    outer = min(size.width, size.height) / 2
    if outer == 0:
        return ()
    inner = max(0.0, outer - thickness)
    cx, cy = size.width / 2, size.height / 2
    edges = []
    for index in range(segments):
        angle = math.tau * index / segments
        x, y = math.sin(angle), -math.cos(angle)
        edges.append((Point(cx + outer * x, cy + outer * y), Point(cx + inner * x, cy + inner * y)))
    edges.append(edges[0])
    return tuple(_ring_wedge(a, b, inner_b, inner_a)
                 for (a, inner_a), (b, inner_b) in pairwise(edges))
