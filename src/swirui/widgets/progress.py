"""Retained determinate progress widgets for SwirUI."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Color, CornerRadius, Path2D, Point, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_DEFAULT_TRACK = Color.from_hex("#172632")
_DEFAULT_FILL = Color.from_hex("#0A98F0")
_DEFAULT_DISABLED_TRACK = Color.from_hex("#202A31")
_DEFAULT_DISABLED_FILL = Color.from_hex("#51636E")
_TRANSPARENT = Color(0.0, 0.0, 0.0, 0.0)


class _ProgressBase(Widget):
    """Shared finite range/value contract for determinate progress widgets."""

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
        self._minimum = self._finite(minimum, "minimum")
        self._maximum = self._finite(maximum, "maximum")
        if self._maximum <= self._minimum:
            raise ValueError("maximum must be greater than minimum.")
        self._value = self._clamp(self._finite(value, "value"))
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
        self._sync_accessible_value()

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
        normalized = self._clamp(self._finite(value, "value"))
        if normalized == self._value:
            return
        old_value = self._value
        self._value = normalized
        self._sync_accessible_value()
        self.invalidate(reason="value")
        self.emit(
            "changed",
            old_value=old_value,
            value=normalized,
            progress=self.progress,
        )

    @property
    def progress(self) -> float:
        return (self._value - self._minimum) / (self._maximum - self._minimum)

    def set_value(self, value: float) -> _ProgressBase:
        self.value = value
        return self

    def _clamp(self, value: float) -> float:
        return min(self._maximum, max(self._minimum, value))

    def _sync_accessible_value(self) -> None:
        self.accessible_value = f"{self.progress * 100.0:.0f}%"

    @staticmethod
    def _finite(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite.")
        return normalized


class ProgressBar(_ProgressBase):
    """Horizontal determinate progress bar compiled to retained GPU rectangles."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        track_color: Color | None = None,
        fill_color: Color | None = None,
        corner_radius: float | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._track_color = track_color or _DEFAULT_TRACK
        self._fill_color = fill_color or _DEFAULT_FILL
        if corner_radius is not None:
            corner_radius = float(corner_radius)
            if not math.isfinite(corner_radius) or corner_radius < 0.0:
                raise ValueError("corner_radius must be finite and non-negative.")
        self._corner_radius = corner_radius
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
        radius = (
            min(self.bounds.height * 0.5, self.bounds.width * 0.5)
            if self._corner_radius is None
            else min(self._corner_radius, self.bounds.height * 0.5, self.bounds.width * 0.5)
        )
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            hit_testable=False,
        )
        if self.bounds.width <= 0.0 or self.bounds.height <= 0.0:
            return root
        track_color = self._track_color if self.enabled else _DEFAULT_DISABLED_TRACK
        fill_color = self._fill_color if self.enabled else _DEFAULT_DISABLED_FILL
        root.add(
            SceneNode(
                key=f"{self.key}:track",
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.bounds,
                fill=track_color,
                corner_radius=CornerRadius.uniform(radius),
                hit_testable=False,
            )
        )
        fill_width = self.bounds.width * self.progress
        if fill_width > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:fill",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(self.bounds.x, self.bounds.y, fill_width, self.bounds.height),
                    z_index=1,
                    fill=fill_color,
                    corner_radius=CornerRadius.uniform(min(radius, fill_width * 0.5)),
                    hit_testable=False,
                )
            )
        return root


class ProgressRing(_ProgressBase):
    """Determinate annular progress indicator rendered as retained GPU paths."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        thickness: float = 6.0,
        track_color: Color | None = None,
        fill_color: Color | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._thickness = float(thickness)
        if not math.isfinite(self._thickness) or self._thickness <= 0.0:
            raise ValueError("thickness must be finite and greater than zero.")
        self._track_color = track_color or _DEFAULT_TRACK
        self._fill_color = fill_color or _DEFAULT_FILL
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

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            hit_testable=False,
        )
        size = min(self.bounds.width, self.bounds.height)
        if size <= 0.0:
            return root
        ring_bounds = Rect(
            self.bounds.x + ((self.bounds.width - size) * 0.5),
            self.bounds.y + ((self.bounds.height - size) * 0.5),
            size,
            size,
        )
        thickness = min(self._thickness, size * 0.45)
        if thickness <= 0.0:
            return root
        root.add(
            SceneNode(
                key=f"{self.key}:track",
                kind=SceneNodeKind.PATH,
                bounds=ring_bounds,
                path=_annular_sector(size, thickness, 1.0),
                fill=self._track_color if self.enabled else _DEFAULT_DISABLED_TRACK,
                hit_testable=False,
            )
        )
        if self.progress > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:fill",
                    kind=SceneNodeKind.PATH,
                    bounds=ring_bounds,
                    z_index=1,
                    path=_annular_sector(size, thickness, self.progress),
                    fill=self._fill_color if self.enabled else _DEFAULT_DISABLED_FILL,
                    hit_testable=False,
                )
            )
        return root


def _annular_sector(size: float, thickness: float, progress: float) -> Path2D:
    """Create a deterministic simple polygon for one clockwise ring sector."""

    outer_radius = size * 0.5
    inner_radius = outer_radius - thickness
    if outer_radius <= 0.0 or inner_radius <= 0.0:
        raise ValueError("Ring geometry requires positive inner and outer radii.")
    bounded = min(1.0, max(0.0, float(progress)))
    sweep = max(1.0e-4, bounded * (math.tau - 1.0e-4))
    segments = max(2, math.ceil(64 * max(bounded, 0.02)))
    start = -math.pi * 0.5
    center = outer_radius

    outer = tuple(
        Point(
            center + (outer_radius * math.cos(start + (sweep * index / segments))),
            center + (outer_radius * math.sin(start + (sweep * index / segments))),
        )
        for index in range(segments + 1)
    )
    inner = tuple(
        Point(
            center + (inner_radius * math.cos(start + (sweep * index / segments))),
            center + (inner_radius * math.sin(start + (sweep * index / segments))),
        )
        for index in range(segments, -1, -1)
    )
    return Path2D((*outer, *inner))
