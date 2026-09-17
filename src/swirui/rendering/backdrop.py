"""Backdrop-aware blur primitives for SwirUI retained scenes.

A :class:`BackdropBlur` node is a painter-order boundary rather than a painted
surface. The GPU renderer renders everything before the node, snapshots and
blurs that already-composited backdrop, composites the blurred pixels only
inside the node bounds, and then continues with the node's descendants and the
rest of the scene. This keeps foreground labels and controls sharp while the
content behind a glass-like surface is blurred.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import CornerRadius, Rect
from .scene import SceneNode, SceneNodeKind

_MAX_BACKDROP_BLUR_RADIUS = 64.0


@dataclass(frozen=True, slots=True)
class BackdropBlur:
    """Describe a retained, DPI-independent backdrop blur boundary.

    ``radius`` is expressed in logical DIPs and converted to physical pixels by
    the active renderer. ``corner_radius`` masks the blurred sample to the same
    rounded geometry used by ordinary SwirUI surfaces. Descendants are clipped
    to the backdrop bounds by default so a panel can attach its tint, border and
    foreground content directly to the blur node without leaking outside it.
    """

    radius: float = 18.0
    corner_radius: CornerRadius = field(default_factory=lambda: CornerRadius.uniform(16.0))

    def __post_init__(self) -> None:
        if not math.isfinite(self.radius):
            raise ValueError("Backdrop blur radius must be finite.")
        if not 0.0 < self.radius <= _MAX_BACKDROP_BLUR_RADIUS:
            raise ValueError(
                f"Backdrop blur radius must be in the range (0, {_MAX_BACKDROP_BLUR_RADIUS}]."
            )

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        z_index: int = 0,
        clip_children: bool = True,
    ) -> SceneNode:
        """Create a non-hit-testable painter-order backdrop boundary."""

        if not key:
            raise ValueError("Backdrop blur scene keys cannot be empty.")
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("Backdrop blur bounds must have positive dimensions.")
        return SceneNode(
            key=key,
            kind=SceneNodeKind.BACKDROP_BLUR,
            bounds=bounds,
            z_index=z_index,
            corner_radius=self.corner_radius,
            blur_radius=self.radius,
            clip_to_bounds=clip_children,
            hit_testable=False,
        )
