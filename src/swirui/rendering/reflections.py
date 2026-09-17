"""Retained specular reflection bands for the Visual Engine.

Reflections compile to ordinary clipped ``LinearGradient`` path geometry so they
reuse SwirUI's existing HiDPI-aware persistent Rust/wgpu path pipeline. The effect
is decorative by construction and never participates in pointer hit testing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from swirui.core.config import VisualQuality

from .geometry import Color, Point, Rect
from .gradients import GradientStop, LinearGradient
from .scene import SceneNode

_DEFAULT_REFLECTION_STEPS = 48
_MAX_REFLECTION_STEPS = 256

_REFLECTION_QUALITY_STEPS: dict[VisualQuality, int] = {
    VisualQuality.AUTO: 48,
    VisualQuality.PERFORMANCE: 12,
    VisualQuality.BALANCED: 24,
    VisualQuality.QUALITY: 48,
    VisualQuality.ULTRA: 72,
    VisualQuality.CINEMATIC: 96,
}


@dataclass(frozen=True, slots=True)
class Reflection:
    """A soft retained specular band clipped to a logical rectangular surface.

    ``angle_degrees`` describes the gradient axis in screen coordinates. The
    visible reflection band is perpendicular to that axis. ``position`` and
    ``width`` are normalized across the full projected bounds, making the effect
    deterministic across window sizes and DPI scales.
    """

    color: Color = field(default_factory=lambda: Color(1.0, 1.0, 1.0, 0.28))
    angle_degrees: float = 22.0
    position: float = 0.36
    width: float = 0.18
    steps: int = _DEFAULT_REFLECTION_STEPS

    def __post_init__(self) -> None:
        if any(
            not math.isfinite(value)
            for value in (self.angle_degrees, self.position, self.width)
        ):
            raise ValueError("Reflection geometry must use finite values.")
        if not 0.0 < self.position < 1.0:
            raise ValueError("Reflection position must be in the range (0, 1).")
        if not 0.0 < self.width <= 2.0:
            raise ValueError("Reflection width must be in the range (0, 2].")
        if not 2 <= self.steps <= _MAX_REFLECTION_STEPS:
            raise ValueError(
                f"Reflection steps must be between 2 and {_MAX_REFLECTION_STEPS}."
            )

    def with_quality(self, quality: VisualQuality) -> Reflection:
        """Return this reflection with a deterministic quality-aware path budget."""

        try:
            steps = _REFLECTION_QUALITY_STEPS[quality]
        except KeyError as exc:  # pragma: no cover - defensive for foreign enum values.
            raise ValueError(f"Unsupported visual quality: {quality!r}.") from exc
        return replace(self, steps=steps)

    def resolved_gradient(self) -> LinearGradient:
        """Resolve the specular band to a normalized multi-stop linear gradient."""

        direction = math.radians(self.angle_degrees)
        dx = math.cos(direction)
        dy = math.sin(direction)
        span = abs(dx) + abs(dy)
        start = Point(0.5 - dx * span * 0.5, 0.5 - dy * span * 0.5)
        end = Point(0.5 + dx * span * 0.5, 0.5 + dy * span * 0.5)

        transparent = Color(self.color.r, self.color.g, self.color.b, 0.0)
        half_width = self.width * 0.5
        left = max(0.0, self.position - half_width)
        right = min(1.0, self.position + half_width)

        stops: list[GradientStop] = [GradientStop(0.0, transparent)]
        if left > 0.0:
            stops.append(GradientStop(left, transparent))
        stops.append(GradientStop(self.position, self.color))
        if right < 1.0:
            stops.append(GradientStop(right, transparent))
        stops.append(GradientStop(1.0, transparent))
        return LinearGradient(start=start, end=end, stops=tuple(stops))

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode:
        """Build a clipped, non-interactive retained reflection subtree."""

        node = self.resolved_gradient().to_scene_node(
            key,
            bounds,
            steps=self.steps,
            opacity=opacity,
            z_index=z_index,
        )
        for descendant in node.walk():
            descendant.hit_testable = False
        return node
