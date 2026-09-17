"""Retained depth, perspective and pointer-driven parallax primitives.

The Visual Engine keeps public geometry in logical device-independent pixels. This
module projects a rectangular surface through a deterministic 3D perspective
transform and emits an ordinary retained ``Path2D`` node, so the existing clipped,
HiDPI-aware persistent wgpu path pipeline renders it without a parallel backend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import Color, Path2D, Point, Rect
from .scene import SceneNode, SceneNodeKind

_MAX_ROTATION_DEGREES = 80.0
_CAMERA_EPSILON = 1.0e-6


def _validate_finite(name: str, *values: float) -> None:
    if any(not math.isfinite(value) for value in values):
        raise ValueError(f"{name} must use finite values.")


@dataclass(frozen=True, slots=True)
class PerspectivePlane:
    """Project a logical rectangle into a retained perspective quadrilateral.

    ``rotation_x_degrees`` tilts the top/bottom edges toward or away from the
    viewer. ``rotation_y_degrees`` tilts the left/right edges. ``depth`` translates
    the plane toward the camera when positive. ``perspective`` is the logical-DIP
    camera distance and must stay in front of every projected corner.

    The resulting scene node is a normal filled ``Path2D`` and therefore inherits
    existing clipping, compositing, HiDPI scaling, hit testing and persistent GPU
    path rendering.
    """

    rotation_x_degrees: float = 0.0
    rotation_y_degrees: float = 0.0
    perspective: float = 900.0
    depth: float = 0.0
    origin: Point = field(default_factory=lambda: Point(0.5, 0.5))

    def __post_init__(self) -> None:
        _validate_finite(
            "Perspective-plane geometry",
            self.rotation_x_degrees,
            self.rotation_y_degrees,
            self.perspective,
            self.depth,
            self.origin.x,
            self.origin.y,
        )
        if abs(self.rotation_x_degrees) > _MAX_ROTATION_DEGREES:
            raise ValueError(
                f"rotation_x_degrees must be between -{_MAX_ROTATION_DEGREES} and "
                f"{_MAX_ROTATION_DEGREES}."
            )
        if abs(self.rotation_y_degrees) > _MAX_ROTATION_DEGREES:
            raise ValueError(
                f"rotation_y_degrees must be between -{_MAX_ROTATION_DEGREES} and "
                f"{_MAX_ROTATION_DEGREES}."
            )
        if self.perspective <= 0.0:
            raise ValueError("perspective must be greater than zero.")
        if not 0.0 <= self.origin.x <= 1.0 or not 0.0 <= self.origin.y <= 1.0:
            raise ValueError("origin coordinates must be normalized to the range [0, 1].")

    def projected_corners(self, bounds: Rect) -> tuple[Point, Point, Point, Point]:
        """Return projected corners in absolute logical-DIP coordinates."""

        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("Perspective-plane bounds must have positive dimensions.")

        pivot_x = bounds.x + bounds.width * self.origin.x
        pivot_y = bounds.y + bounds.height * self.origin.y
        rotation_x = math.radians(self.rotation_x_degrees)
        rotation_y = math.radians(self.rotation_y_degrees)
        cos_x = math.cos(rotation_x)
        sin_x = math.sin(rotation_x)
        cos_y = math.cos(rotation_y)
        sin_y = math.sin(rotation_y)

        result: list[Point] = []
        for point in (
            Point(bounds.x, bounds.y),
            Point(bounds.right, bounds.y),
            Point(bounds.right, bounds.bottom),
            Point(bounds.x, bounds.bottom),
        ):
            local_x = point.x - pivot_x
            local_y = point.y - pivot_y

            # Rotate around X, then Y. Positive Z points toward the camera.
            rotated_y = local_y * cos_x
            rotated_z = local_y * sin_x
            rotated_x = local_x * cos_y + rotated_z * sin_y
            rotated_z = -local_x * sin_y + rotated_z * cos_y + self.depth

            denominator = self.perspective - rotated_z
            if denominator <= _CAMERA_EPSILON:
                raise ValueError(
                    "Perspective plane crosses or reaches the camera plane; increase "
                    "perspective or reduce depth/rotation."
                )
            scale = self.perspective / denominator
            result.append(
                Point(
                    pivot_x + rotated_x * scale,
                    pivot_y + rotated_y * scale,
                )
            )

        return result[0], result[1], result[2], result[3]

    def projected_path(self, bounds: Rect) -> tuple[Rect, Path2D]:
        """Return the projected bounding box plus local retained polygon geometry."""

        corners = self.projected_corners(bounds)
        left = min(point.x for point in corners)
        top = min(point.y for point in corners)
        right = max(point.x for point in corners)
        bottom = max(point.y for point in corners)
        projected_bounds = Rect(left, top, right - left, bottom - top)
        path = Path2D.polygon(
            *(Point(point.x - left, point.y - top) for point in corners)
        )
        return projected_bounds, path

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        fill: Color,
        opacity: float = 1.0,
        z_index: int = 0,
        hit_testable: bool = True,
    ) -> SceneNode:
        """Build a retained GPU-path node containing the projected surface."""

        if not key:
            raise ValueError("Perspective-plane scene keys cannot be empty.")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Perspective-plane opacity must be between 0.0 and 1.0.")
        projected_bounds, path = self.projected_path(bounds)
        return SceneNode(
            key=key,
            kind=SceneNodeKind.PATH,
            bounds=projected_bounds,
            fill=fill,
            path=path,
            opacity=opacity,
            z_index=z_index,
            hit_testable=hit_testable,
        )


@dataclass(frozen=True, slots=True)
class Parallax:
    """Map a pointer position to a deterministic perspective tilt.

    Applications can rebuild only the affected retained node when pointer input
    changes. The model clamps input outside the viewport, so pointer capture or
    fast movement cannot generate unbounded rotations.
    """

    max_rotation_x_degrees: float = 8.0
    max_rotation_y_degrees: float = 12.0
    perspective: float = 900.0
    depth: float = 0.0
    origin: Point = field(default_factory=lambda: Point(0.5, 0.5))

    def __post_init__(self) -> None:
        _validate_finite(
            "Parallax geometry",
            self.max_rotation_x_degrees,
            self.max_rotation_y_degrees,
            self.perspective,
            self.depth,
            self.origin.x,
            self.origin.y,
        )
        if not 0.0 <= self.max_rotation_x_degrees <= _MAX_ROTATION_DEGREES:
            raise ValueError(
                f"max_rotation_x_degrees must be between 0 and {_MAX_ROTATION_DEGREES}."
            )
        if not 0.0 <= self.max_rotation_y_degrees <= _MAX_ROTATION_DEGREES:
            raise ValueError(
                f"max_rotation_y_degrees must be between 0 and {_MAX_ROTATION_DEGREES}."
            )
        PerspectivePlane(
            perspective=self.perspective,
            depth=self.depth,
            origin=self.origin,
        )

    def resolve(self, pointer: Point, viewport: Rect) -> PerspectivePlane:
        """Resolve pointer coordinates into a bounded perspective plane."""

        _validate_finite("Parallax pointer", pointer.x, pointer.y)
        if viewport.width <= 0.0 or viewport.height <= 0.0:
            raise ValueError("Parallax viewport must have positive dimensions.")

        normalized_x = (pointer.x - (viewport.x + viewport.width * 0.5)) / (
            viewport.width * 0.5
        )
        normalized_y = (pointer.y - (viewport.y + viewport.height * 0.5)) / (
            viewport.height * 0.5
        )
        normalized_x = max(-1.0, min(1.0, normalized_x))
        normalized_y = max(-1.0, min(1.0, normalized_y))
        return PerspectivePlane(
            rotation_x_degrees=-normalized_y * self.max_rotation_x_degrees,
            rotation_y_degrees=normalized_x * self.max_rotation_y_degrees,
            perspective=self.perspective,
            depth=self.depth,
            origin=self.origin,
        )

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        pointer: Point,
        viewport: Rect,
        fill: Color,
        opacity: float = 1.0,
        z_index: int = 0,
        hit_testable: bool = True,
    ) -> SceneNode:
        """Project ``bounds`` from ``pointer`` and return a retained path node."""

        return self.resolve(pointer, viewport).to_scene_node(
            key,
            bounds,
            fill=fill,
            opacity=opacity,
            z_index=z_index,
            hit_testable=hit_testable,
        )
