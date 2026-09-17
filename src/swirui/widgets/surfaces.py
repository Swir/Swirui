"""Retained container surfaces for the SwirUI core-widget layer."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole
from swirui.rendering.effects import DropShadow
from swirui.rendering.geometry import Color, CornerRadius, Point, Rect
from swirui.rendering.materials import FrostedGlass
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_PANEL_BACKGROUND = Color.from_hex("#0A1823")
_PANEL_BORDER = Color.from_hex("#203D4F")
_CARD_BACKGROUND = Color.from_hex("#0B1B28")
_CARD_BORDER = Color.from_hex("#2A5166")
_TRANSPARENT = Color(0.0, 0.0, 0.0, 0.0)
_SURFACE_Z = -20
_BORDER_Z = -30
_SHADOW_Z = -40


def _inset_rect(bounds: Rect, inset: float) -> Rect:
    if inset == 0.0:
        return bounds
    width = bounds.width - (2.0 * inset)
    height = bounds.height - (2.0 * inset)
    if width <= 0.0 or height <= 0.0:
        raise ValueError("border_width is too large for the current bounds.")
    return Rect(bounds.x + inset, bounds.y + inset, width, height)


def _inset_radius(radius: CornerRadius, inset: float) -> CornerRadius:
    return CornerRadius(
        max(0.0, radius.top_left - inset),
        max(0.0, radius.top_right - inset),
        max(0.0, radius.bottom_right - inset),
        max(0.0, radius.bottom_left - inset),
    )


class Panel(Widget):
    """Retained visual container with optional border and child clipping."""

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        background: Color | None = None,
        border_color: Color | None = None,
        border_width: float = 0.0,
        corner_radius: float = 0.0,
        clip_to_bounds: bool = False,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._background = background or _PANEL_BACKGROUND
        self._border_color = border_color or _PANEL_BORDER
        self._border_width = self._validate_non_negative(border_width, "border_width")
        radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._corner_radius = CornerRadius.uniform(radius)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    @property
    def background(self) -> Color:
        return self._background

    @background.setter
    def background(self, value: Color) -> None:
        if value == self._background:
            return
        self._background = value
        self.invalidate(reason="background")

    @property
    def border_color(self) -> Color:
        return self._border_color

    @border_color.setter
    def border_color(self, value: Color) -> None:
        if value == self._border_color:
            return
        self._border_color = value
        self.invalidate(reason="border_color")

    @property
    def border_width(self) -> float:
        return self._border_width

    @border_width.setter
    def border_width(self, value: float) -> None:
        normalized = self._validate_non_negative(value, "border_width")
        if normalized == self._border_width:
            return
        self._border_width = normalized
        self.invalidate(reason="border_width")

    @property
    def corner_radius(self) -> CornerRadius:
        return self._corner_radius

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=self.clip_to_bounds,
            hit_testable=False,
        )
        inner_bounds = _inset_rect(self.bounds, self.border_width)
        inner_radius = _inset_radius(self.corner_radius, self.border_width)
        if self.border_width > 0.0 and self.border_color.a > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:border",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=self.bounds,
                    fill=self.border_color,
                    corner_radius=self.corner_radius,
                    z_index=_BORDER_Z,
                    hit_testable=False,
                )
            )
        if self.background.a > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:surface",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=inner_bounds,
                    fill=self.background,
                    corner_radius=inner_radius,
                    z_index=_SURFACE_Z,
                    hit_testable=False,
                )
            )
        return root

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized


class Frame(Panel):
    """Transparent bordered container for grouping retained widget content."""

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        border_color: Color | None = None,
        border_width: float = 1.0,
        corner_radius: float = 8.0,
        clip_to_bounds: bool = False,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            key=key,
            background=_TRANSPARENT,
            border_color=border_color,
            border_width=border_width,
            corner_radius=corner_radius,
            clip_to_bounds=clip_to_bounds,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )


class Card(Panel):
    """Elevated retained content card built from the verified shadow/rectangle path."""

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        background: Color | None = None,
        border_color: Color | None = None,
        border_width: float = 1.0,
        corner_radius: float = 18.0,
        shadow: DropShadow | None = None,
        show_shadow: bool = True,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            key=key,
            background=background or _CARD_BACKGROUND,
            border_color=border_color or _CARD_BORDER,
            border_width=border_width,
            corner_radius=corner_radius,
            clip_to_bounds=False,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._shadow = (
            None
            if not show_shadow
            else shadow
            or DropShadow(
                color=Color(0.0, 0.0, 0.0, 0.32),
                offset=Point(0.0, 7.0),
                blur_radius=18.0,
                spread=1.0,
                steps=8,
            )
        )

    def build_scene_node(self) -> SceneNode:
        root = super().build_scene_node()
        if self._shadow is not None:
            root.add(
                self._shadow.to_scene_node(
                    f"{self.key}:shadow",
                    self.bounds,
                    corner_radius=self.corner_radius,
                    z_index=_SHADOW_Z,
                )
            )
        return root


class GlassCard(Widget):
    """Container backed by the native painter-order frosted-glass material path."""

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        material: FrostedGlass | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._material = material or FrostedGlass()
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    @property
    def material(self) -> FrostedGlass:
        return self._material

    @material.setter
    def material(self, value: FrostedGlass) -> None:
        if value == self._material:
            return
        self._material = value
        self.invalidate(reason="material")

    def build_scene_node(self) -> SceneNode:
        node = self.material.to_scene_node(self.key, self.bounds, z_index=self.z_index)
        node.opacity = self.opacity
        node.hit_testable = False
        return node
