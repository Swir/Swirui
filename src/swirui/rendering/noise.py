"""Deterministic retained noise/grain overlays for the GPU scene pipeline."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from swirui.core import VisualQuality

from .geometry import Color, CornerRadius, Rect
from .scene import SceneNode, SceneNodeKind

_MAX_NOISE_SAMPLES = 512
_NOISE_QUALITY_SAMPLES: dict[VisualQuality, int] = {
    VisualQuality.AUTO: 48,
    VisualQuality.PERFORMANCE: 16,
    VisualQuality.BALANCED: 32,
    VisualQuality.QUALITY: 64,
    VisualQuality.ULTRA: 96,
    VisualQuality.CINEMATIC: 128,
}


def _noise_rect(
    bounds: Rect,
    *,
    size: float,
    sample_index: int,
    state: int,
) -> tuple[Rect, int]:
    """Return one deterministic grain rectangle and the next PRNG state."""

    state = (1_664_525 * state + 1_013_904_223) & 0xFFFF_FFFF
    x_unit = state / 4_294_967_296.0
    state = (1_664_525 * state + 1_013_904_223 + sample_index) & 0xFFFF_FFFF
    y_unit = state / 4_294_967_296.0
    travel_x = max(0.0, bounds.width - size)
    travel_y = max(0.0, bounds.height - size)
    return (
        Rect(bounds.x + x_unit * travel_x, bounds.y + y_unit * travel_y, size, size),
        state,
    )


@dataclass(frozen=True, slots=True)
class Noise:
    """Retained deterministic micro-grain rendered by the native rectangle batch.

    The effect is generated only when the SceneGraph is built. Repeated frames
    reuse the same retained geometry, avoiding per-frame randomness, image
    uploads and a separate renderer path. ``with_quality`` changes only the
    sample budget while preserving geometry size, color and seed semantics.
    """

    samples: int = 48
    size: float = 1.25
    color: Color = field(default_factory=lambda: Color(1.0, 1.0, 1.0, 0.045))
    seed: int = 0x51A7_2026

    def __post_init__(self) -> None:
        if not 0 <= self.samples <= _MAX_NOISE_SAMPLES:
            raise ValueError(f"Noise samples must be between 0 and {_MAX_NOISE_SAMPLES}.")
        if not math.isfinite(self.size):
            raise ValueError("Noise size must be finite.")
        if not 0.25 <= self.size <= 8.0:
            raise ValueError("Noise size must be between 0.25 and 8 logical DIPs.")

    def with_quality(self, quality: VisualQuality) -> Noise:
        """Return this effect with the retained sample budget for ``quality``."""

        try:
            samples = _NOISE_QUALITY_SAMPLES[quality]
        except KeyError as exc:  # pragma: no cover - defensive for foreign enum values.
            raise ValueError(f"Unsupported visual quality: {quality!r}.") from exc
        return replace(self, samples=samples)

    def to_scene_node(self, key: str, bounds: Rect, *, z_index: int = 0) -> SceneNode:
        """Build a clipped, non-hit-testable retained noise subtree."""

        root = SceneNode(
            key=key,
            kind=SceneNodeKind.GROUP,
            bounds=bounds,
            z_index=z_index,
            clip_to_bounds=True,
            hit_testable=False,
        )
        if self.samples == 0 or self.color.a == 0.0:
            return root

        state = self.seed & 0xFFFF_FFFF
        dot_radius = CornerRadius.uniform(self.size * 0.5)
        for index in range(self.samples):
            sample_bounds, state = _noise_rect(
                bounds,
                size=self.size,
                sample_index=index,
                state=state,
            )
            root.add(
                SceneNode(
                    key=f"{key}:{index}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=sample_bounds,
                    fill=self.color,
                    corner_radius=dot_radius,
                    z_index=index,
                    hit_testable=False,
                )
            )
        return root
