"""Immutable GPU color-matrix filters for SwirUI's post-processing pipeline."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

ColorMatrix = tuple[
    float, float, float, float, float,
    float, float, float, float, float,
    float, float, float, float, float,
    float, float, float, float, float,
]

_IDENTITY: ColorMatrix = (
    1.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 1.0, 0.0,
)


def _amount(name: str, value: float, *, maximum: float = 1.0) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if not 0.0 <= value <= maximum:
        raise ValueError(f"{name} must be between 0 and {maximum:g}.")
    return float(value)


def _matrix(values: Iterable[float]) -> ColorMatrix:
    data = tuple(float(value) for value in values)
    if len(data) != 20:
        raise ValueError("ColorFilter requires exactly 20 matrix values.")
    if any(not math.isfinite(value) for value in data):
        raise ValueError("ColorFilter matrix values must be finite.")
    return data  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ColorFilter:
    """A 4x5 affine RGBA color transform executed by the native GPU core.

    The matrix is row-major and follows the conventional 4x5 color-matrix form::

        r' = m00*r + m01*g + m02*b + m03*a + m04
        g' = m10*r + m11*g + m12*b + m13*a + m14
        b' = m20*r + m21*g + m22*b + m23*a + m24
        a' = m30*r + m31*g + m32*b + m33*a + m34

    Values are not artificially restricted to ``0..1`` because useful contrast,
    exposure and composed transforms can temporarily exceed that range. The native
    shader clamps the final output before presentation.
    """

    matrix: ColorMatrix = _IDENTITY

    def __post_init__(self) -> None:
        object.__setattr__(self, "matrix", _matrix(self.matrix))

    @classmethod
    def identity(cls) -> ColorFilter:
        """Return an identity transform."""

        return cls(_IDENTITY)

    @classmethod
    def brightness(cls, amount: float) -> ColorFilter:
        """Scale RGB brightness while preserving alpha (``1`` is neutral)."""

        value = _amount("brightness amount", amount, maximum=4.0)
        return cls(
            (
                value, 0.0, 0.0, 0.0, 0.0,
                0.0, value, 0.0, 0.0, 0.0,
                0.0, 0.0, value, 0.0, 0.0,
                0.0, 0.0, 0.0, 1.0, 0.0,
            )
        )

    @classmethod
    def contrast(cls, amount: float) -> ColorFilter:
        """Adjust RGB contrast around 0.5 while preserving alpha."""

        value = _amount("contrast amount", amount, maximum=4.0)
        offset = 0.5 * (1.0 - value)
        return cls(
            (
                value, 0.0, 0.0, 0.0, offset,
                0.0, value, 0.0, 0.0, offset,
                0.0, 0.0, value, 0.0, offset,
                0.0, 0.0, 0.0, 1.0, 0.0,
            )
        )

    @classmethod
    def saturation(cls, amount: float) -> ColorFilter:
        """Adjust color saturation (``0`` grayscale, ``1`` neutral)."""

        value = _amount("saturation amount", amount, maximum=4.0)
        lr, lg, lb = 0.2126, 0.7152, 0.0722
        inverse = 1.0 - value
        return cls(
            (
                lr * inverse + value, lg * inverse, lb * inverse, 0.0, 0.0,
                lr * inverse, lg * inverse + value, lb * inverse, 0.0, 0.0,
                lr * inverse, lg * inverse, lb * inverse + value, 0.0, 0.0,
                0.0, 0.0, 0.0, 1.0, 0.0,
            )
        )

    @classmethod
    def grayscale(cls, amount: float = 1.0) -> ColorFilter:
        """Blend toward luminance grayscale by ``amount`` in ``0..1``."""

        value = _amount("grayscale amount", amount)
        return cls.saturation(1.0 - value)

    @classmethod
    def invert(cls, amount: float = 1.0) -> ColorFilter:
        """Blend RGB toward its inverse by ``amount`` in ``0..1``."""

        value = _amount("invert amount", amount)
        scale = 1.0 - 2.0 * value
        return cls(
            (
                scale, 0.0, 0.0, 0.0, value,
                0.0, scale, 0.0, 0.0, value,
                0.0, 0.0, scale, 0.0, value,
                0.0, 0.0, 0.0, 1.0, 0.0,
            )
        )

    @classmethod
    def sepia(cls, amount: float = 1.0) -> ColorFilter:
        """Blend RGB toward the standard sepia transform by ``amount``."""

        value = _amount("sepia amount", amount)
        inverse = 1.0 - value
        sepia = (
            (0.393, 0.769, 0.189),
            (0.349, 0.686, 0.168),
            (0.272, 0.534, 0.131),
        )
        rows: list[float] = []
        for row_index, row in enumerate(sepia):
            rows.extend(
                inverse * (1.0 if row_index == column else 0.0) + value * coefficient
                for column, coefficient in enumerate(row)
            )
            rows.extend((0.0, 0.0))
        rows.extend((0.0, 0.0, 0.0, 1.0, 0.0))
        return cls(_matrix(rows))

    @classmethod
    def hue_rotate(cls, degrees: float) -> ColorFilter:
        """Rotate RGB hue by ``degrees`` while preserving luminance and alpha."""

        if not math.isfinite(degrees):
            raise ValueError("hue rotation must be finite.")
        angle = math.radians(degrees % 360.0)
        cosine = math.cos(angle)
        sine = math.sin(angle)
        return cls(
            (
                0.213 + cosine * 0.787 - sine * 0.213,
                0.715 - cosine * 0.715 - sine * 0.715,
                0.072 - cosine * 0.072 + sine * 0.928,
                0.0,
                0.0,
                0.213 - cosine * 0.213 + sine * 0.143,
                0.715 + cosine * 0.285 + sine * 0.140,
                0.072 - cosine * 0.072 - sine * 0.283,
                0.0,
                0.0,
                0.213 - cosine * 0.213 - sine * 0.787,
                0.715 - cosine * 0.715 + sine * 0.715,
                0.072 + cosine * 0.928 + sine * 0.072,
                0.0,
                0.0,
                0.0, 0.0, 0.0, 1.0, 0.0,
            )
        )

    def then(self, following: ColorFilter) -> ColorFilter:
        """Compose this transform followed by ``following`` into one GPU pass."""

        first_rows, first_offset = self._rows_and_offset()
        next_rows, next_offset = following._rows_and_offset()
        rows: list[list[float]] = []
        offset: list[float] = []
        for output in range(4):
            rows.append(
                [
                    sum(next_rows[output][k] * first_rows[k][column] for k in range(4))
                    for column in range(4)
                ]
            )
            offset.append(
                sum(next_rows[output][k] * first_offset[k] for k in range(4))
                + next_offset[output]
            )
        flattened: list[float] = []
        for row, bias in zip(rows, offset, strict=True):
            flattened.extend((*row, bias))
        return ColorFilter(_matrix(flattened))

    def native_values(self) -> tuple[float, ...]:
        """Pack the affine matrix as five WGSL-aligned ``vec4<f32>`` values."""

        rows, offset = self._rows_and_offset()
        return tuple(value for row in rows for value in row) + tuple(offset)

    def _rows_and_offset(self) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]:
        rows = tuple(tuple(self.matrix[row * 5 + column] for column in range(4)) for row in range(4))
        offset = tuple(self.matrix[row * 5 + 4] for row in range(4))
        return rows, offset
