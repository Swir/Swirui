"""Directional retained surface lighting for the Visual Engine.

Adaptive lighting composes two verified GPU-friendly retained effects: a shadow
projected away from a directional light and a softer highlight projected toward
it. The public model stays in logical DIPs while the existing renderer handles
HiDPI scaling, clipping, compositing and native wgpu rectangle batching.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from swirui.core import VisualQuality

from .effects import DropShadow, effect_quality_profile
from .geometry import Color, CornerRadius, Point, Rect
from .scene import SceneNode, SceneNodeKind

_MAX_LIGHTING_STEPS = 64


def _union_bounds(first: Rect, second: Rect) -> Rect:
    left = min(first.x, second.x)
    top = min(first.y, second.y)
    right = max(first.right, second.right)
    bottom = max(first.bottom, second.bottom)
    return Rect(left, top, right - left, bottom - top)


@dataclass(frozen=True, slots=True)
class AdaptiveLighting:
    """Retained directional lighting for an elevated rounded surface.

    ``light_direction_degrees`` points from the surface toward the light in
    screen coordinates (0° right, 90° down), matching :class:`DynamicShadow`.
    The shadow lobe projects away from the light while a lower-amplitude highlight
    lobe projects toward it. Both are retained rectangle stacks, so moving the
    light only rebuilds scene geometry and never replaces the persistent GPU
    context.
    """

    elevation: float = 14.0
    light_direction_degrees: float = 270.0
    light_altitude_degrees: float = 55.0
    shadow_color: Color = field(default_factory=lambda: Color(0.0, 0.0, 0.0, 0.34))
    highlight_color: Color = field(default_factory=lambda: Color(0.72, 0.90, 1.0, 0.20))
    shadow_softness: float = 1.55
    highlight_softness: float = 0.70
    highlight_offset_ratio: float = 0.32
    spread: float = 0.0
    steps: int = 16

    def __post_init__(self) -> None:
        values = (
            self.elevation,
            self.light_direction_degrees,
            self.light_altitude_degrees,
            self.shadow_softness,
            self.highlight_softness,
            self.highlight_offset_ratio,
            self.spread,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Adaptive-lighting geometry must use finite values.")
        if self.elevation < 0.0:
            raise ValueError("Adaptive-lighting elevation cannot be negative.")
        if not 0.0 < self.light_altitude_degrees <= 90.0:
            raise ValueError(
                "Adaptive-lighting light_altitude_degrees must be in the range (0, 90]."
            )
        if self.shadow_softness < 0.0:
            raise ValueError("Adaptive-lighting shadow_softness cannot be negative.")
        if self.highlight_softness < 0.0:
            raise ValueError("Adaptive-lighting highlight_softness cannot be negative.")
        if not 0.0 <= self.highlight_offset_ratio <= 1.0:
            raise ValueError(
                "Adaptive-lighting highlight_offset_ratio must be between 0.0 and 1.0."
            )
        if self.spread < 0.0:
            raise ValueError("Adaptive-lighting spread cannot be negative.")
        if not 1 <= self.steps <= _MAX_LIGHTING_STEPS:
            raise ValueError(
                f"Adaptive-lighting steps must be between 1 and {_MAX_LIGHTING_STEPS}."
            )

    def with_quality(self, quality: VisualQuality) -> AdaptiveLighting:
        """Return this light model with a deterministic quality-aware layer budget."""

        return replace(self, steps=effect_quality_profile(quality).dynamic_shadow_steps)

    def resolved_lobes(self) -> tuple[DropShadow, DropShadow]:
        """Resolve the light model to shadow and highlight retained lobes."""

        altitude = math.radians(self.light_altitude_degrees)
        projection = (
            0.0
            if self.elevation == 0.0 or self.light_altitude_degrees == 90.0
            else self.elevation / math.tan(altitude)
        )
        direction = math.radians(self.light_direction_degrees)
        light_x = math.cos(direction)
        light_y = math.sin(direction)
        shadow_offset = Point(-light_x * projection, -light_y * projection)
        highlight_offset = Point(
            light_x * projection * self.highlight_offset_ratio,
            light_y * projection * self.highlight_offset_ratio,
        )
        return (
            DropShadow(
                color=self.shadow_color,
                offset=shadow_offset,
                blur_radius=self.elevation * self.shadow_softness,
                spread=self.spread,
                steps=self.steps,
            ),
            DropShadow(
                color=self.highlight_color,
                offset=highlight_offset,
                blur_radius=self.elevation * self.highlight_softness,
                spread=0.0,
                steps=self.steps,
            ),
        )

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        corner_radius: CornerRadius | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode:
        """Build a retained, non-interactive directional lighting subtree."""

        if not key:
            raise ValueError("Adaptive-lighting scene keys cannot be empty.")
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("Adaptive-lighting bounds must have positive dimensions.")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Adaptive-lighting opacity must be between 0.0 and 1.0.")

        if self.elevation == 0.0 or (
            self.shadow_color.a == 0.0 and self.highlight_color.a == 0.0
        ):
            return SceneNode(
                key=key,
                kind=SceneNodeKind.GROUP,
                bounds=bounds,
                opacity=opacity,
                z_index=z_index,
                hit_testable=False,
            )

        radius = CornerRadius() if corner_radius is None else corner_radius
        shadow, highlight = self.resolved_lobes()
        children: list[SceneNode] = []
        if self.shadow_color.a > 0.0:
            children.append(
                shadow.to_scene_node(
                    f"{key}:shadow",
                    bounds,
                    corner_radius=radius,
                    z_index=0,
                )
            )
        if self.highlight_color.a > 0.0:
            children.append(
                highlight.to_scene_node(
                    f"{key}:highlight",
                    bounds,
                    corner_radius=radius,
                    z_index=1,
                )
            )

        group_bounds = children[0].bounds
        for child in children[1:]:
            group_bounds = _union_bounds(group_bounds, child.bounds)
        group = SceneNode(
            key=key,
            kind=SceneNodeKind.GROUP,
            bounds=group_bounds,
            opacity=opacity,
            z_index=z_index,
            hit_testable=False,
        )
        group.add(*children)
        return group
