"""Retained progress widgets."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Color, CornerRadius, Path2D, Point, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

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

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float,
        minimum: float,
        maximum: float,
        key: str | None,
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
    """Horizontal determinate progress bar rendered by retained rectangles."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            value=value,
            minimum=minimum,
            maximum=maximum,
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    def build_scene_node(self) -> SceneNode:
        radius = min(self.bounds.height / 2.0, self.bounds.width / 2.0)
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRACK if self.enabled else _DISABLED,
            corner_radius=CornerRadius.uniform(radius),
            hit_testable=False,
        )
        fill_width = self.bounds.width * self.progress
        if fill_width > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:fill",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(
                        self.bounds.x,
                        self.bounds.y,
                        fill_width,
                        self.bounds.height,
                    ),
                    z_index=1,
                    fill=_FILL if self.enabled else _DISABLED,
                    corner_radius=CornerRadius.uniform(min(radius, fill_width / 2.0)),
                    hit_testable=False,
                )
            )
        return root


class ProgressRing(_ProgressWidget):
    """Determinate progress ring compiled to a bounded set of retained paths."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        thickness: float = 6.0,
        segments: int = 48,
        key: str | None = None,
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
        super().__init__(
            bounds=bounds,
            value=value,
            minimum=minimum,
            maximum=maximum,
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    @property
    def thickness(self) -> float:
        return self._thickness

    @property
    def segments(self) -> int:
        return self._segments

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            hit_testable=False,
        )
        outer_radius = max(0.0, min(self.bounds.width, self.bounds.height) / 2.0)
        if outer_radius <= 0.0:
            return root
        inner_radius = max(0.0, outer_radius - min(self._thickness, outer_radius))
        center_x = self.bounds.width / 2.0
        center_y = self.bounds.height / 2.0
        active_segments = round(self._segments * self.progress)
        for index in range(self._segments):
            start = -math.pi / 2.0 + (2.0 * math.pi * index / self._segments)
            end = -math.pi / 2.0 + (2.0 * math.pi * (index + 1) / self._segments)
            outer_a = Point(
                center_x + math.cos(start) * outer_radius,
                center_y + math.sin(start) * outer_radius,
            )
            outer_b = Point(
                center_x + math.cos(end) * outer_radius,
                center_y + math.sin(end) * outer_radius,
            )
            if inner_radius > 0.0:
                inner_b = Point(
                    center_x + math.cos(end) * inner_radius,
                    center_y + math.sin(end) * inner_radius,
                )
                inner_a = Point(
                    center_x + math.cos(start) * inner_radius,
                    center_y + math.sin(start) * inner_radius,
                )
                path = Path2D.polygon(outer_a, outer_b, inner_b, inner_a)
            else:
                path = Path2D.polygon(outer_a, outer_b, Point(center_x, center_y))
            active = index < active_segments
            color = _FILL if active and self.enabled else _TRACK
            if not self.enabled:
                color = _DISABLED
            root.add(
                SceneNode(
                    key=f"{self.key}:segment:{index}",
                    kind=SceneNodeKind.PATH,
                    bounds=Rect(
                        self.bounds.x,
                        self.bounds.y,
                        self.bounds.width,
                        self.bounds.height,
                    ),
                    z_index=1,
                    fill=color,
                    path=path,
                    hit_testable=False,
                )
            )
        return root
