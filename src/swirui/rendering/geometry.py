"""Geometry and color primitives shared by rendering backends."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Size:
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Size dimensions cannot be negative.")


@dataclass(frozen=True, slots=True)
class Point:
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Rectangle dimensions cannot be negative.")

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    def contains(self, point: Point) -> bool:
        return self.x <= point.x <= self.right and self.y <= point.y <= self.bottom

    def intersects(self, other: Rect) -> bool:
        return not (
            other.right < self.x
            or other.x > self.right
            or other.bottom < self.y
            or other.y > self.bottom
        )


@dataclass(frozen=True, slots=True)
class CornerRadius:
    top_left: float = 0.0
    top_right: float = 0.0
    bottom_right: float = 0.0
    bottom_left: float = 0.0

    def __post_init__(self) -> None:
        if min(self.top_left, self.top_right, self.bottom_right, self.bottom_left) < 0:
            raise ValueError("Corner radii cannot be negative.")

    @classmethod
    def uniform(cls, radius: float) -> CornerRadius:
        return cls(radius, radius, radius, radius)


@dataclass(frozen=True, slots=True)
class Color:
    """Linear framework color represented as normalized RGBA channels."""

    r: float
    g: float
    b: float
    a: float = 1.0

    def __post_init__(self) -> None:
        if any(channel < 0.0 or channel > 1.0 for channel in (self.r, self.g, self.b, self.a)):
            raise ValueError("Color channels must be between 0.0 and 1.0.")

    @classmethod
    def from_hex(cls, value: str) -> Color:
        text = value.strip().removeprefix("#")
        if len(text) not in (6, 8):
            raise ValueError("Hex colors must use RRGGBB or RRGGBBAA format.")
        try:
            r = int(text[0:2], 16) / 255.0
            g = int(text[2:4], 16) / 255.0
            b = int(text[4:6], 16) / 255.0
            a = int(text[6:8], 16) / 255.0 if len(text) == 8 else 1.0
        except ValueError as exc:
            raise ValueError("Invalid hexadecimal color.") from exc
        return cls(r, g, b, a)

    def with_alpha(self, alpha: float) -> Color:
        return Color(self.r, self.g, self.b, alpha)
