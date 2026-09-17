"""Retained glass-like materials built on painter-order GPU backdrop blur.

The material helpers in this module do not introduce a second renderer path.
They compose the verified :class:`BackdropBlur` boundary with ordinary retained
rounded-rectangle layers, so tint, border, luminosity and acrylic grain remain
HiDPI-aware, clip-aware and batchable by the persistent native wgpu renderer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from swirui.core import VisualQuality

from .backdrop import BackdropBlur
from .geometry import Color, CornerRadius, Rect
from .scene import SceneNode, SceneNodeKind

_MAX_MATERIAL_BORDER_WIDTH = 16.0
_MAX_GRAIN_SAMPLES = 192
_MATERIAL_BORDER_Z = -30
_MATERIAL_TINT_Z = -20
_MATERIAL_LUMINOSITY_Z = -10
_MATERIAL_GRAIN_Z = -5
_ACRYLIC_QUALITY_SAMPLES: dict[VisualQuality, int] = {
    VisualQuality.AUTO: 40,
    VisualQuality.PERFORMANCE: 12,
    VisualQuality.BALANCED: 24,
    VisualQuality.QUALITY: 48,
    VisualQuality.ULTRA: 72,
    VisualQuality.CINEMATIC: 96,
}


def _validate_material_geometry(*, border_width: float, grain_size: float | None = None) -> None:
    if not math.isfinite(border_width):
        raise ValueError("Material border_width must be finite.")
    if not 0.0 <= border_width <= _MAX_MATERIAL_BORDER_WIDTH:
        raise ValueError(
            "Material border_width must be between 0 and "
            f"{_MAX_MATERIAL_BORDER_WIDTH} logical DIPs."
        )
    if grain_size is not None:
        if not math.isfinite(grain_size):
            raise ValueError("Acrylic grain_size must be finite.")
        if not 0.25 <= grain_size <= 8.0:
            raise ValueError("Acrylic grain_size must be between 0.25 and 8 logical DIPs.")


def _inset_rect(bounds: Rect, inset: float) -> Rect:
    if inset == 0.0:
        return bounds
    width = bounds.width - inset * 2.0
    height = bounds.height - inset * 2.0
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Material border_width is too large for the requested bounds.")
    return Rect(bounds.x + inset, bounds.y + inset, width, height)


def _inset_radius(radius: CornerRadius, inset: float) -> CornerRadius:
    return CornerRadius(
        max(0.0, radius.top_left - inset),
        max(0.0, radius.top_right - inset),
        max(0.0, radius.bottom_right - inset),
        max(0.0, radius.bottom_left - inset),
    )


def _rectangle_layer(
    key: str,
    bounds: Rect,
    color: Color,
    radius: CornerRadius,
    *,
    z_index: int,
) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.RECTANGLE,
        bounds=bounds,
        fill=color,
        corner_radius=radius,
        z_index=z_index,
        hit_testable=False,
    )


def _add_base_material_layers(
    root: SceneNode,
    *,
    key: str,
    bounds: Rect,
    corner_radius: CornerRadius,
    tint: Color,
    border_color: Color,
    border_width: float,
) -> Rect:
    inner_bounds = _inset_rect(bounds, border_width)
    inner_radius = _inset_radius(corner_radius, border_width)
    if border_width > 0.0 and border_color.a > 0.0:
        root.add(
            _rectangle_layer(
                f"{key}:border",
                bounds,
                border_color,
                corner_radius,
                z_index=_MATERIAL_BORDER_Z,
            )
        )
    root.add(
        _rectangle_layer(
            f"{key}:tint",
            inner_bounds,
            tint,
            inner_radius,
            z_index=_MATERIAL_TINT_Z,
        )
    )
    return inner_bounds


def _grain_rect(
    bounds: Rect,
    *,
    size: float,
    sample_index: int,
    state: int,
) -> tuple[Rect, int]:
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
class FrostedGlass:
    """A retained frosted-glass surface with native backdrop blur.

    The returned scene node is a non-interactive backdrop boundary. Applications
    can attach labels and controls directly to it; internal decoration uses
    reserved negative z-indices so ordinary child content at the default z-index
    stays sharp and paints above the material layers.
    """

    blur_radius: float = 22.0
    tint: Color = field(default_factory=lambda: Color(0.055, 0.095, 0.17, 0.34))
    border_color: Color = field(default_factory=lambda: Color(0.76, 0.90, 1.0, 0.26))
    border_width: float = 1.0
    corner_radius: CornerRadius = field(default_factory=lambda: CornerRadius.uniform(24.0))

    def __post_init__(self) -> None:
        _validate_material_geometry(border_width=self.border_width)
        # Reuse BackdropBlur's public radius validation so both APIs stay aligned.
        BackdropBlur(radius=self.blur_radius, corner_radius=self.corner_radius)

    def to_scene_node(self, key: str, bounds: Rect, *, z_index: int = 0) -> SceneNode:
        """Build the retained backdrop/tint/border subtree for ``bounds``."""

        root = BackdropBlur(
            radius=self.blur_radius,
            corner_radius=self.corner_radius,
        ).to_scene_node(key, bounds, z_index=z_index, clip_children=True)
        _add_base_material_layers(
            root,
            key=key,
            bounds=bounds,
            corner_radius=self.corner_radius,
            tint=self.tint,
            border_color=self.border_color,
            border_width=self.border_width,
        )
        return root


@dataclass(frozen=True, slots=True)
class Acrylic:
    """Acrylic-like material with backdrop blur, tint, luminosity and micro-grain.

    ``grain_samples`` controls a deterministic retained micro-grain overlay. The
    tiny rounded rectangles reuse the native instanced rectangle batch; no image
    upload or per-frame random generation is required. ``with_quality`` adapts
    only grain density, preserving material geometry, tint and blur semantics.
    """

    blur_radius: float = 30.0
    tint: Color = field(default_factory=lambda: Color(0.035, 0.075, 0.15, 0.52))
    luminosity: Color = field(default_factory=lambda: Color(0.72, 0.86, 1.0, 0.075))
    grain_color: Color = field(default_factory=lambda: Color(1.0, 1.0, 1.0, 0.045))
    border_color: Color = field(default_factory=lambda: Color(0.74, 0.88, 1.0, 0.24))
    border_width: float = 1.0
    corner_radius: CornerRadius = field(default_factory=lambda: CornerRadius.uniform(26.0))
    grain_samples: int = 40
    grain_size: float = 1.25
    grain_seed: int = 0x5A17_2026

    def __post_init__(self) -> None:
        _validate_material_geometry(border_width=self.border_width, grain_size=self.grain_size)
        BackdropBlur(radius=self.blur_radius, corner_radius=self.corner_radius)
        if not 0 <= self.grain_samples <= _MAX_GRAIN_SAMPLES:
            raise ValueError(
                f"Acrylic grain_samples must be between 0 and {_MAX_GRAIN_SAMPLES}."
            )

    def with_quality(self, quality: VisualQuality) -> Acrylic:
        """Return this material with deterministic grain density for ``quality``."""

        try:
            samples = _ACRYLIC_QUALITY_SAMPLES[quality]
        except KeyError as exc:  # pragma: no cover - defensive for foreign enum values.
            raise ValueError(f"Unsupported visual quality: {quality!r}.") from exc
        return replace(self, grain_samples=samples)

    def to_scene_node(self, key: str, bounds: Rect, *, z_index: int = 0) -> SceneNode:
        """Build one retained acrylic-like surface for ``bounds``."""

        root = BackdropBlur(
            radius=self.blur_radius,
            corner_radius=self.corner_radius,
        ).to_scene_node(key, bounds, z_index=z_index, clip_children=True)
        inner_bounds = _add_base_material_layers(
            root,
            key=key,
            bounds=bounds,
            corner_radius=self.corner_radius,
            tint=self.tint,
            border_color=self.border_color,
            border_width=self.border_width,
        )
        inner_radius = _inset_radius(self.corner_radius, self.border_width)
        root.add(
            _rectangle_layer(
                f"{key}:luminosity",
                inner_bounds,
                self.luminosity,
                inner_radius,
                z_index=_MATERIAL_LUMINOSITY_Z,
            )
        )

        if self.grain_samples == 0 or self.grain_color.a == 0.0:
            return root

        # Keep procedural grain away from rounded corner cut-outs. The compositor
        # owns the rounded backdrop mask while SceneGraph clipping is rectangular.
        edge_guard = max(
            inner_radius.top_left,
            inner_radius.top_right,
            inner_radius.bottom_right,
            inner_radius.bottom_left,
        )
        grain_bounds = inner_bounds
        if (
            edge_guard > 0.0
            and inner_bounds.width > edge_guard * 2.0
            and inner_bounds.height > edge_guard * 2.0
        ):
            grain_bounds = Rect(
                inner_bounds.x + edge_guard,
                inner_bounds.y + edge_guard,
                inner_bounds.width - edge_guard * 2.0,
                inner_bounds.height - edge_guard * 2.0,
            )

        grain_group = SceneNode(
            key=f"{key}:grain",
            kind=SceneNodeKind.GROUP,
            bounds=grain_bounds,
            z_index=_MATERIAL_GRAIN_Z,
            clip_to_bounds=True,
            hit_testable=False,
        )
        state = self.grain_seed & 0xFFFF_FFFF
        dot_radius = CornerRadius.uniform(self.grain_size * 0.5)
        for index in range(self.grain_samples):
            grain_rect, state = _grain_rect(
                grain_bounds,
                size=self.grain_size,
                sample_index=index,
                state=state,
            )
            grain_group.add(
                _rectangle_layer(
                    f"{key}:grain:{index}",
                    grain_rect,
                    self.grain_color,
                    dot_radius,
                    z_index=index,
                )
            )
        root.add(grain_group)
        return root
