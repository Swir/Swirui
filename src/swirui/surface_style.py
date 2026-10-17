"""Portable material and decorative perspective choices for themed surfaces."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .rendering.depth import PerspectivePlane
from .rendering.effects import DropShadow, Glow
from .rendering.geometry import Color, CornerRadius, Point, Rect
from .rendering.materials import Acrylic, FrostedGlass
from .rendering.scene import SceneNode, SceneNodeKind

if TYPE_CHECKING:
    from .theme import Theme


@dataclass(frozen=True, slots=True)
class SurfaceStyle:
    """Reusable, bounded decoration; child content keeps its layout and hit area.

    Colors follow the theme. Perspective layers are decorative projected planes,
    not a 3D viewport or a perspective transform of interactive child controls.
    """

    kind: Literal["solid", "glass", "acrylic"] = "solid"
    blur_radius: float = 22
    tint_opacity: float = 0.72
    border_opacity: float = 0.7
    border_width: float = 1
    elevation: float = 8
    glow_radius: float = 0
    glow_opacity: float = 0.2
    depth_layers: int = 0
    depth_spacing: float = 8
    tilt_x: float = 10
    tilt_y: float = -12
    grain_samples: int = 24

    def __post_init__(self) -> None:
        if self.kind not in ("solid", "glass", "acrylic"):
            raise ValueError("SurfaceStyle kind must be solid, glass or acrylic.")
        ranges = {
            "blur_radius": (0, 64), "tint_opacity": (0, 1), "border_opacity": (0, 1),
            "border_width": (0, 16), "elevation": (0, 64), "glow_radius": (0, 64),
            "glow_opacity": (0, 1), "depth_spacing": (0, 24),
            "tilt_x": (-35, 35), "tilt_y": (-35, 35),
        }
        for name, (low, high) in ranges.items():
            value = getattr(self, name)
            if (type(value) not in (int, float) or not low <= value <= high
                    or not math.isfinite(value)):
                raise ValueError(f"SurfaceStyle {name} must be finite and in [{low}, {high}].")
        for name, high in (("depth_layers", 8), ("grain_samples", 96)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= high:
                raise ValueError(f"SurfaceStyle {name} must be an integer in [0, {high}].")
        if self.kind != "solid" and self.blur_radius == 0:
            raise ValueError("Glass and acrylic blur_radius must be greater than zero.")

    def to_scene_node(self, key: str, bounds: Rect, theme: Theme) -> SceneNode:
        root = SceneNode(key, SceneNodeKind.GROUP, bounds, hit_testable=False)
        if bounds.width <= 0 or bounds.height <= 0:
            return root
        radius = CornerRadius.uniform(theme.control_radius)
        accent = theme.surface_color("accent")
        tint = theme.surface_color("surface")
        border = theme.surface_color("border")
        for index in range(self.depth_layers):
            distance = (self.depth_layers - index) * self.depth_spacing
            plane = PerspectivePlane(
                rotation_x_degrees=self.tilt_x, rotation_y_degrees=self.tilt_y,
                perspective=max(900, math.hypot(bounds.width, bounds.height) * 2),
            )
            root.add(plane.to_scene_node(
                f"{key}:depth:{index}",
                Rect(bounds.x + distance * 0.45, bounds.y + distance,
                     bounds.width, bounds.height),
                fill=Color(accent.r, accent.g, accent.b, accent.a * 0.13),
                z_index=-80 + index, hit_testable=False,
            ))
        if self.elevation:
            root.add(DropShadow(
                color=Color(0, 0, 0, 0.32), offset=Point(0, self.elevation),
                blur_radius=self.elevation * 2, steps=8,
            ).to_scene_node(f"{key}:shadow", bounds, corner_radius=radius, z_index=-60))
        if self.glow_radius and self.glow_opacity:
            root.add(Glow(
                color=Color(accent.r, accent.g, accent.b, accent.a * self.glow_opacity),
                blur_radius=self.glow_radius, steps=8,
            ).to_scene_node(f"{key}:glow", bounds, corner_radius=radius, z_index=-50))
        border_width = min(self.border_width, min(bounds.width, bounds.height) * 0.25)
        if self.kind in ("glass", "acrylic"):
            tint = Color(tint.r, tint.g, tint.b, tint.a * self.tint_opacity)
            border = Color(border.r, border.g, border.b, border.a * self.border_opacity)
            material: FrostedGlass | Acrylic
            if self.kind == "glass":
                material = FrostedGlass(
                    blur_radius=self.blur_radius, tint=tint, border_color=border,
                    border_width=border_width, corner_radius=radius,
                )
            else:
                material = Acrylic(
                    blur_radius=self.blur_radius, tint=tint, border_color=border,
                    border_width=border_width, corner_radius=radius,
                    grain_samples=self.grain_samples,
                )
            root.add(material.to_scene_node(f"{key}:material", bounds, z_index=-20))
        else:
            if border_width and self.border_opacity:
                root.add(SceneNode(
                    f"{key}:border", SceneNodeKind.RECTANGLE, bounds,
                    fill=Color(border.r, border.g, border.b, border.a * self.border_opacity),
                    corner_radius=radius, z_index=-30, hit_testable=False,
                ))
            inner = Rect(bounds.x + border_width, bounds.y + border_width,
                         bounds.width - 2 * border_width, bounds.height - 2 * border_width)
            root.add(SceneNode(
                f"{key}:surface", SceneNodeKind.RECTANGLE, inner, fill=tint,
                corner_radius=CornerRadius.uniform(max(0, theme.control_radius - border_width)),
                z_index=-20, hit_testable=False,
            ))
        return root
