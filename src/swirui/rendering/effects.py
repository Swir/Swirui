"""Retained visual-effect primitives built from verified GPU scene nodes.

Visual effects deliberately compose SwirUI's existing instanced rounded-rectangle
pipeline instead of introducing parallel rendering paths. Drop shadows, elevation-
aware dynamic shadows and glows all expand into deterministic non-interactive
rounded-rectangle layers whose alpha follows a normalized Gaussian-like falloff.
The resulting subtrees remain retained, HiDPI-aware, clip/compositing compatible
and batchable by the persistent native wgpu renderer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from swirui.core.config import VisualQuality

from .geometry import Color, CornerRadius, Point, Rect
from .scene import SceneNode, SceneNodeKind

_DEFAULT_EFFECT_STEPS = 12
_MAX_EFFECT_STEPS = 64
_GAUSSIAN_FALLOFF = 2.5


@dataclass(frozen=True, slots=True)
class EffectQualityProfile:
    """Visual-effect tessellation budgets for one :class:`VisualQuality` level.

    These budgets control retained geometry density only; they do not silently
    alter layout, colors, light direction or effect extents. Applications may use
    the existing ``AppConfig.visual_quality`` value to derive deterministic effect
    detail while retaining an explicit ``steps=`` override on each primitive.
    """

    shadow_steps: int
    glow_steps: int
    dynamic_shadow_steps: int

    def __post_init__(self) -> None:
        for value in (self.shadow_steps, self.glow_steps, self.dynamic_shadow_steps):
            if not 1 <= value <= _MAX_EFFECT_STEPS:
                raise ValueError(
                    f"Effect quality steps must be between 1 and {_MAX_EFFECT_STEPS}."
                )


_EFFECT_QUALITY_PROFILES: dict[VisualQuality, EffectQualityProfile] = {
    VisualQuality.AUTO: EffectQualityProfile(12, 12, 16),
    VisualQuality.PERFORMANCE: EffectQualityProfile(4, 4, 6),
    VisualQuality.BALANCED: EffectQualityProfile(8, 8, 10),
    VisualQuality.QUALITY: EffectQualityProfile(16, 16, 20),
    VisualQuality.ULTRA: EffectQualityProfile(24, 24, 28),
    VisualQuality.CINEMATIC: EffectQualityProfile(32, 32, 40),
}


def effect_quality_profile(quality: VisualQuality) -> EffectQualityProfile:
    """Return the immutable retained-effect budget for ``quality``."""

    try:
        return _EFFECT_QUALITY_PROFILES[quality]
    except KeyError as exc:  # pragma: no cover - defensive for foreign enum values.
        raise ValueError(f"Unsupported visual quality: {quality!r}.") from exc


def _validate_effect_parameters(
    *,
    name: str,
    offset: Point,
    blur_radius: float,
    spread: float,
    steps: int,
) -> None:
    values = (offset.x, offset.y, blur_radius, spread)
    if any(not math.isfinite(value) for value in values):
        raise ValueError(f"{name} geometry must use finite values.")
    if blur_radius < 0.0:
        raise ValueError(f"{name} blur_radius cannot be negative.")
    if spread < 0.0:
        raise ValueError(f"{name} spread cannot be negative.")
    if not 1 <= steps <= _MAX_EFFECT_STEPS:
        raise ValueError(f"{name} steps must be between 1 and {_MAX_EFFECT_STEPS}.")


def _expanded_bounds(bounds: Rect, offset: Point, extent: float) -> Rect:
    return Rect(
        bounds.x + offset.x - extent,
        bounds.y + offset.y - extent,
        bounds.width + extent * 2.0,
        bounds.height + extent * 2.0,
    )


def _effect_layer(
    *,
    key: str,
    layer_index: int,
    bounds: Rect,
    radius: CornerRadius,
    color: Color,
    offset: Point,
    extent: float,
    alpha: float,
) -> SceneNode:
    return SceneNode(
        key=f"{key}:layer:{layer_index}",
        kind=SceneNodeKind.RECTANGLE,
        bounds=_expanded_bounds(bounds, offset, extent),
        fill=Color(color.r, color.g, color.b, alpha),
        corner_radius=CornerRadius(
            radius.top_left + extent,
            radius.top_right + extent,
            radius.bottom_right + extent,
            radius.bottom_left + extent,
        ),
        hit_testable=False,
    )


def _gaussian_layers(
    *,
    key: str,
    bounds: Rect,
    corner_radius: CornerRadius,
    color: Color,
    offset: Point,
    blur_radius: float,
    spread: float,
    steps: int,
    opacity: float,
    z_index: int,
) -> SceneNode:
    if not key:
        raise ValueError("Effect scene keys cannot be empty.")
    if bounds.width <= 0.0 or bounds.height <= 0.0:
        raise ValueError("Effect bounds must have positive dimensions.")
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("Effect opacity must be between 0.0 and 1.0.")

    maximum_extent = spread + blur_radius
    group = SceneNode(
        key=key,
        kind=SceneNodeKind.GROUP,
        bounds=_expanded_bounds(bounds, offset, maximum_extent),
        opacity=opacity,
        z_index=z_index,
        hit_testable=False,
    )

    if blur_radius == 0.0:
        group.add(
            _effect_layer(
                key=key,
                layer_index=0,
                bounds=bounds,
                radius=corner_radius,
                color=color,
                offset=offset,
                extent=spread,
                alpha=color.a,
            )
        )
        return group

    weights = tuple(
        math.exp(-_GAUSSIAN_FALLOFF * (index / steps) ** 2)
        for index in range(1, steps + 1)
    )
    total_weight = sum(weights)

    # Paint the widest/softest layer first and the tightest layer last.
    for layer_index, index in enumerate(range(steps, 0, -1)):
        normalized_radius = index / steps
        extent = spread + blur_radius * normalized_radius
        alpha = color.a * weights[index - 1] / total_weight
        group.add(
            _effect_layer(
                key=key,
                layer_index=layer_index,
                bounds=bounds,
                radius=corner_radius,
                color=color,
                offset=offset,
                extent=extent,
                alpha=alpha,
            )
        )
    return group


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
    steps: int = _DEFAULT_EFFECT_STEPS

    def __post_init__(self) -> None:
        _validate_effect_parameters(
            name="Drop-shadow",
            offset=self.offset,
            blur_radius=self.blur_radius,
            spread=self.spread,
            steps=self.steps,
        )

    def with_quality(self, quality: VisualQuality) -> DropShadow:
        """Return this effect with its layer budget adapted to ``quality``."""

        return replace(self, steps=effect_quality_profile(quality).shadow_steps)

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

        radius = CornerRadius() if corner_radius is None else corner_radius
        return _gaussian_layers(
            key=key,
            bounds=bounds,
            corner_radius=radius,
            color=self.color,
            offset=self.offset,
            blur_radius=self.blur_radius,
            spread=self.spread,
            steps=self.steps,
            opacity=opacity,
            z_index=z_index,
        )


@dataclass(frozen=True, slots=True)
class Glow:
    """A centered retained glow halo rendered by the native GPU rectangle batch."""

    color: Color = field(default_factory=lambda: Color(0.0, 0.65, 1.0, 0.45))
    blur_radius: float = 20.0
    spread: float = 0.0
    steps: int = _DEFAULT_EFFECT_STEPS

    def __post_init__(self) -> None:
        _validate_effect_parameters(
            name="Glow",
            offset=Point(),
            blur_radius=self.blur_radius,
            spread=self.spread,
            steps=self.steps,
        )

    def with_quality(self, quality: VisualQuality) -> Glow:
        """Return this glow with its retained layer budget adapted to ``quality``."""

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
        """Build a centered, non-hit-testable glow subtree for ``bounds``."""

        radius = CornerRadius() if corner_radius is None else corner_radius
        return _gaussian_layers(
            key=key,
            bounds=bounds,
            corner_radius=radius,
            color=self.color,
            offset=Point(),
            blur_radius=self.blur_radius,
            spread=self.spread,
            steps=self.steps,
            opacity=opacity,
            z_index=z_index,
        )


@dataclass(frozen=True, slots=True)
class DynamicShadow:
    """Elevation-aware shadow derived from a directional light source.

    ``light_direction_degrees`` points from the surface toward the light in
    screen-space coordinates, where 0° points right and 90° points down. The
    shadow is projected in the opposite direction. ``light_altitude_degrees``
    controls projection length: 90° is directly overhead while lower values cast
    progressively longer shadows. Rebuilding a scene with changed light/elevation
    parameters updates the effect while preserving the persistent GPU context.
    """

    elevation: float = 12.0
    color: Color = field(default_factory=lambda: Color(0.0, 0.0, 0.0, 0.36))
    light_direction_degrees: float = 270.0
    light_altitude_degrees: float = 55.0
    softness: float = 1.65
    spread: float = 0.0
    steps: int = 16

    def __post_init__(self) -> None:
        values = (
            self.elevation,
            self.light_direction_degrees,
            self.light_altitude_degrees,
            self.softness,
            self.spread,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Dynamic-shadow geometry must use finite values.")
        if self.elevation < 0.0:
            raise ValueError("Dynamic-shadow elevation cannot be negative.")
        if not 0.0 < self.light_altitude_degrees <= 90.0:
            raise ValueError(
                "Dynamic-shadow light_altitude_degrees must be in the range (0, 90]."
            )
        if self.softness < 0.0:
            raise ValueError("Dynamic-shadow softness cannot be negative.")
        if self.spread < 0.0:
            raise ValueError("Dynamic-shadow spread cannot be negative.")
        if not 1 <= self.steps <= _MAX_EFFECT_STEPS:
            raise ValueError(
                f"Dynamic-shadow steps must be between 1 and {_MAX_EFFECT_STEPS}."
            )

    def with_quality(self, quality: VisualQuality) -> DynamicShadow:
        """Return this light model with its layer budget adapted to ``quality``."""

        return replace(self, steps=effect_quality_profile(quality).dynamic_shadow_steps)

    def resolved_shadow(self) -> DropShadow:
        """Resolve light/elevation parameters to a concrete retained drop shadow."""

        altitude_radians = math.radians(self.light_altitude_degrees)
        projection = (
            0.0
            if self.elevation == 0.0 or self.light_altitude_degrees == 90.0
            else self.elevation / math.tan(altitude_radians)
        )
        shadow_direction = math.radians(self.light_direction_degrees + 180.0)
        offset = Point(
            math.cos(shadow_direction) * projection,
            math.sin(shadow_direction) * projection,
        )
        return DropShadow(
            color=self.color,
            offset=offset,
            blur_radius=self.elevation * self.softness,
            spread=self.spread,
            steps=self.steps,
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
        """Build the current light/elevation projection as retained GPU layers."""

        return self.resolved_shadow().to_scene_node(
            key,
            bounds,
            corner_radius=corner_radius,
            opacity=opacity,
            z_index=z_index,
        )
