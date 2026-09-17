"""Retained source-bloom effect built on SwirUI's verified GPU scene pipeline.

Bloom is intentionally explicit about its source geometry: applications mark a
luminous surface and SwirUI compiles a two-band light spill around those bounds.
The result is retained rounded-rectangle geometry, so it inherits the existing
HiDPI conversion, clipping, opacity composition, batching and persistent wgpu
context without introducing a second scene renderer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from swirui.core.config import VisualQuality

from .effects import Glow, effect_quality_profile
from .geometry import Color, CornerRadius, Rect
from .scene import SceneNode, SceneNodeKind

_MAX_BLOOM_STEPS = 64
_OUTER_ENERGY = 0.42
_CORE_RADIUS_RATIO = 0.38


def _expanded_bounds(bounds: Rect, extent: float) -> Rect:
    return Rect(
        bounds.x - extent,
        bounds.y - extent,
        bounds.width + extent * 2.0,
        bounds.height + extent * 2.0,
    )


def _split_steps(steps: int) -> tuple[int, int]:
    """Split one quality budget between wide spill and tighter bloom core."""

    if steps == 1:
        return (1, 0)
    outer_steps = max(1, steps * 2 // 3)
    return (outer_steps, steps - outer_steps)


@dataclass(frozen=True, slots=True)
class Bloom:
    """A retained two-band bloom halo around explicit luminous bounds.

    ``blur_radius`` and ``spread`` are logical DIPs. ``intensity`` scales the
    source color alpha without changing its RGB channels. ``steps`` is the total
    retained layer budget across the wide spill and compact core, so quality
    profiles change GPU work predictably while preserving effect extent.

    This primitive is source-driven rather than a whole-frame luminance-threshold
    pass: callers choose the surface that emits light. That makes it useful for
    neon controls, emissive cards and status accents while keeping retained-scene
    ordering deterministic.
    """

    color: Color = field(default_factory=lambda: Color(0.0, 0.65, 1.0, 0.6))
    blur_radius: float = 32.0
    spread: float = 2.0
    intensity: float = 1.0
    steps: int = 12

    def __post_init__(self) -> None:
        values = (self.blur_radius, self.spread, self.intensity)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Bloom parameters must be finite.")
        if self.blur_radius < 0.0:
            raise ValueError("Bloom blur_radius cannot be negative.")
        if self.spread < 0.0:
            raise ValueError("Bloom spread cannot be negative.")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("Bloom intensity must be between 0.0 and 1.0.")
        if not 1 <= self.steps <= _MAX_BLOOM_STEPS:
            raise ValueError(f"Bloom steps must be between 1 and {_MAX_BLOOM_STEPS}.")

    def with_quality(self, quality: VisualQuality) -> Bloom:
        """Return this bloom using the shared glow budget for ``quality``."""

        return replace(self, steps=effect_quality_profile(quality).glow_steps)

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        corner_radius: CornerRadius | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode:
        """Compile the bloom into retained, non-interactive GPU rectangle layers."""

        if not key:
            raise ValueError("Bloom scene keys cannot be empty.")
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("Bloom bounds must have positive dimensions.")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Bloom opacity must be between 0.0 and 1.0.")

        radius = CornerRadius() if corner_radius is None else corner_radius
        extent = self.spread + self.blur_radius
        group = SceneNode(
            key=key,
            kind=SceneNodeKind.GROUP,
            bounds=_expanded_bounds(bounds, extent),
            opacity=opacity,
            z_index=z_index,
            hit_testable=False,
        )

        outer_steps, core_steps = _split_steps(self.steps)
        bloom_alpha = self.color.a * self.intensity
        if core_steps == 0:
            outer_alpha = bloom_alpha
            core_alpha = 0.0
        else:
            outer_alpha = bloom_alpha * _OUTER_ENERGY
            core_alpha = bloom_alpha - outer_alpha

        outer = Glow(
            color=Color(self.color.r, self.color.g, self.color.b, outer_alpha),
            blur_radius=self.blur_radius,
            spread=self.spread,
            steps=outer_steps,
        ).to_scene_node(
            f"{key}:spill",
            bounds,
            corner_radius=radius,
        )
        group.add(outer)

        if core_steps:
            core = Glow(
                color=Color(self.color.r, self.color.g, self.color.b, core_alpha),
                blur_radius=self.blur_radius * _CORE_RADIUS_RATIO,
                spread=self.spread * 0.5,
                steps=core_steps,
            ).to_scene_node(
                f"{key}:core",
                bounds,
                corner_radius=radius,
                z_index=1,
            )
            group.add(core)

        return group
