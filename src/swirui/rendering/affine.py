"""Backend-neutral affine transform math for retained scene geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import Point, Rect

_DETERMINANT_EPSILON = 1.0e-12
_AXIS_ALIGNMENT_EPSILON = 1.0e-12
_ORIGIN = Point()


@dataclass(frozen=True, slots=True)
class Affine2D:
    """Invertible 2D affine transform expressed in logical-DIP coordinates.

    The matrix maps authored scene coordinates into visual coordinates::

        x' = m11 * x + m12 * y + tx
        y' = m21 * x + m22 * y + ty

    SwirUI keeps this transform independent from layout geometry. That makes it
    suitable for retained visual animation while allowing hit testing to map the
    pointer back into authored coordinates exactly.
    """

    m11: float = 1.0
    m12: float = 0.0
    m21: float = 0.0
    m22: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def __post_init__(self) -> None:
        values = (self.m11, self.m12, self.m21, self.m22, self.tx, self.ty)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Affine2D values must be finite.")
        if abs(self.determinant) <= _DETERMINANT_EPSILON:
            raise ValueError("Affine2D must be invertible.")

    @property
    def determinant(self) -> float:
        return self.m11 * self.m22 - self.m12 * self.m21

    @property
    def is_identity(self) -> bool:
        return (
            self.m11 == 1.0
            and self.m12 == 0.0
            and self.m21 == 0.0
            and self.m22 == 1.0
            and self.tx == 0.0
            and self.ty == 0.0
        )

    @property
    def is_axis_aligned(self) -> bool:
        """Return whether axis-aligned rectangles remain axis-aligned after mapping.

        Translation and independent X/Y scale are axis-aligned. Rotation and shear
        are not. A tiny tolerance absorbs floating-point residue from composed
        transforms such as a mathematically complete turn.
        """

        return (
            abs(self.m12) <= _AXIS_ALIGNMENT_EPSILON
            and abs(self.m21) <= _AXIS_ALIGNMENT_EPSILON
        )

    @classmethod
    def rotation(cls, radians: float, *, origin: Point = _ORIGIN) -> Affine2D:
        """Create a counter-clockwise rotation around ``origin``."""

        angle = float(radians)
        if not math.isfinite(angle):
            raise ValueError("Rotation angle must be finite.")
        if not math.isfinite(origin.x) or not math.isfinite(origin.y):
            raise ValueError("Rotation origin must use finite coordinates.")
        cosine = math.cos(angle)
        sine = math.sin(angle)
        return cls(
            m11=cosine,
            m12=-sine,
            m21=sine,
            m22=cosine,
            tx=origin.x - cosine * origin.x + sine * origin.y,
            ty=origin.y - sine * origin.x - cosine * origin.y,
        )

    @classmethod
    def translation(cls, dx: float, dy: float) -> Affine2D:
        """Create a logical-DIP translation transform."""

        return cls(tx=float(dx), ty=float(dy))

    @classmethod
    def uniform_scale(cls, scale: float, *, origin: Point = _ORIGIN) -> Affine2D:
        """Create a positive uniform scale around ``origin``."""

        normalized = float(scale)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError("Affine2D uniform scale must be finite and greater than zero.")
        if not math.isfinite(origin.x) or not math.isfinite(origin.y):
            raise ValueError("Scale origin must use finite coordinates.")
        return cls(
            m11=normalized,
            m22=normalized,
            tx=origin.x * (1.0 - normalized),
            ty=origin.y * (1.0 - normalized),
        )

    def transform_point(self, point: Point) -> Point:
        """Map one authored point into visual coordinates."""

        return Point(
            self.m11 * point.x + self.m12 * point.y + self.tx,
            self.m21 * point.x + self.m22 * point.y + self.ty,
        )

    def inverse_transform_point(self, point: Point) -> Point:
        """Map one visual point back to authored coordinates without allocating a matrix.

        Pointer routing invokes inverse mapping frequently. Computing the two
        coordinates directly preserves the exact ``inverse().transform_point()``
        result while avoiding a temporary ``Affine2D`` object for every clip and
        candidate in the retained hit-test path.
        """

        determinant = self.determinant
        x = point.x - self.tx
        y = point.y - self.ty
        return Point(
            (self.m22 * x - self.m12 * y) / determinant,
            (-self.m21 * x + self.m11 * y) / determinant,
        )

    def inverse(self) -> Affine2D:
        """Return the exact inverse transform."""

        determinant = self.determinant
        inverse_m11 = self.m22 / determinant
        inverse_m12 = -self.m12 / determinant
        inverse_m21 = -self.m21 / determinant
        inverse_m22 = self.m11 / determinant
        return Affine2D(
            m11=inverse_m11,
            m12=inverse_m12,
            m21=inverse_m21,
            m22=inverse_m22,
            tx=-(inverse_m11 * self.tx + inverse_m12 * self.ty),
            ty=-(inverse_m21 * self.tx + inverse_m22 * self.ty),
        )

    def then(self, following: Affine2D) -> Affine2D:
        """Compose this transform with ``following`` in visual order.

        ``a.then(b)`` applies ``a`` first and then ``b``. The explicit ordering
        keeps nested retained transforms deterministic and avoids matrix-order
        ambiguity at call sites.
        """

        return Affine2D(
            m11=following.m11 * self.m11 + following.m12 * self.m21,
            m12=following.m11 * self.m12 + following.m12 * self.m22,
            m21=following.m21 * self.m11 + following.m22 * self.m21,
            m22=following.m21 * self.m12 + following.m22 * self.m22,
            tx=following.m11 * self.tx + following.m12 * self.ty + following.tx,
            ty=following.m21 * self.tx + following.m22 * self.ty + following.ty,
        )

    def transform_rect_bounds(self, rect: Rect) -> Rect:
        """Return the axis-aligned visual bounds enclosing transformed ``rect``."""

        corners = (
            self.transform_point(Point(rect.x, rect.y)),
            self.transform_point(Point(rect.right, rect.y)),
            self.transform_point(Point(rect.right, rect.bottom)),
            self.transform_point(Point(rect.x, rect.bottom)),
        )
        left = min(point.x for point in corners)
        top = min(point.y for point in corners)
        right = max(point.x for point in corners)
        bottom = max(point.y for point in corners)
        return Rect(left, top, right - left, bottom - top)
