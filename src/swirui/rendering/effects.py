"""Retained visual-effect primitives built from verified GPU scene nodes.

The first Visual Engine effect deliberately composes SwirUI's existing instanced
rounded-rectangle pipeline instead of creating a separate shadow renderer. A
:class:`DropShadow` expands into a deterministic stack of non-interactive rounded
rectangles whose alpha follows a normalized Gaussian-like falloff. The resulting
subtree remains retained, HiDPI-aware and batchable by the native wgpu renderer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import Color, CornerRadius, Point, Rect
from .scene import SceneNode, SceneNodeKind

_DEFAULT_SHADOW_STEPS = 12
_MAX_SHADOW_STEPS = 64
_GAUSSIAN_FALLOFF = 2.5


@dataclass(frozen=True, slots=True)
class DropShadow:
    """A retained rounded-rectangle drop shadow.

    ``blur_radius`` and ``spread`` are expressed in logical DIPs. The effect is
    tessellated once into a small stack of rounded rectangle instances, allowing
    the existing native rectangle pipeline to batch it with ordinary UI surfaces.
    Decorative shadow nodes opt out of SceneGraph hit testing so visual overflow
    never steals pointer input from nearby controls.
    """

    color: Color = field(default_factory=lambda: Color(0.0, 0.0, 0.0, 0.35))
    offset: Point = field(default_factory=lambda: Point(0.0, 8.0))
    blur_radius: float = 24.0
    spread: float = 0.0
    steps: int = _DEFAULT_SHADOW_STEPS

    def __post_init__(self) -> None:
        values = (self.offset.x, self.offset.y, self.blur_radius, self.spread)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Drop-shadow geometry must use finite values.")
        if self.blur_radius < 0.0:
            raise ValueError("Drop-shadow blur_radius cannot be negative.")
        if self.spread < 0.0:
            raise ValueError("Drop-shadow spread cannot be negative.")
        if not 1 <= self.steps <= _MAX_SHADOW_STEPS:
            raise ValueError(
                f"Drop-shadow steps must be between 1 and {_MAX_SHADOW_STEPS}."
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
        """Build a retained, non-hit-testable shadow subtree for ``bounds``."""

        if not key:
            raise ValueError("Drop-shadow scene keys cannot be empty.")
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("Drop-shadow bounds must have positive dimensions.")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Drop-shadow opacity must be between 0.0 and 1.0.")

        radius = CornerRadius() if corner_radius is None else corner_radius
        maximum_extent = self.spread + self.blur_radius
        group_bounds = self._expanded_bounds(bounds, maximum_extent)
        group = SceneNode(
            key=key,
            kind=SceneNodeKind.GROUP,
            bounds=group_bounds,
            opacity=opacity,
            z_index=z_index,
            hit_testable=False,
        )

        if self.blur_radius == 0.0:
            group.add(self._layer(key, bounds, radius, self.spread, self.color.a))
            return group

        weights = tuple(
            math.exp(-_GAUSSIAN_FALLOFF * (index / self.steps) ** 2)
            for index in range(1, self.steps + 1)
        )
        total_weight = sum(weights)

        # Paint the widest/softest layer first and the tightest layer last.
        for index in range(self.steps, 0, -1):
            normalized_radius = index / self.steps
            extent = self.spread + self.blur_radius * normalized_radius
            alpha = self.color.a * weights[index - 1] / total_weight
            group.add(self._layer(key, bounds, radius, extent, alpha))
        return group

    def _expanded_bounds(self, bounds: Rect, extent: float) -> Rect:
        return Rect(
            bounds.x + self.offset.x - extent,
            bounds.y + self.offset.y - extent,
            bounds.width + extent * 2.0,
            bounds.height + extent * 2.0,
        )

    def _layer(
        self,
        key: str,
        bounds: Rect,
        radius: CornerRadius,
        extent: float,
        alpha: float,
    ) -> SceneNode:
        return SceneNode(
            key=key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self._expanded_bounds(bounds, extent),
            fill=Color(self.color.r, self.color.g, self.color.b, alpha),
            corner_radius=CornerRadius(
                radius.top_left + extent,
                radius.top_right + extent,
                radius.bottom_right + extent,
                radius.bottom_left + extent,
            ),
            hit_testable=False,
        )
