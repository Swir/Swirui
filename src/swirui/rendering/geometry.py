"""Geometry and color primitives shared by rendering backends."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


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


Triangle = tuple[Point, Point, Point]


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

    def intersection(self, other: Rect) -> Rect | None:
        """Return the positive-area overlap between two rectangles, if any."""

        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        if right <= left or bottom <= top:
            return None
        return Rect(left, top, right - left, bottom - top)


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
class Path2D:
    """A simple closed polygon path expressed in local logical coordinates.

    The first renderer implementation supports filled straight-line paths. Both
    convex and concave simple polygons are accepted. Validation and deterministic
    ear-clipping tessellation happen once when immutable path geometry is created,
    so retained scenes can reuse the prepared triangle tuple on every frame.
    """

    points: tuple[Point, ...]
    _triangles: tuple[Triangle, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        points = self.points
        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]
        if len(points) < 3:
            raise ValueError("Path2D requires at least three vertices.")
        if any(not math.isfinite(value) for point in points for value in (point.x, point.y)):
            raise ValueError("Path2D vertices must use finite coordinates.")
        if len({(point.x, point.y) for point in points}) != len(points):
            raise ValueError("Path2D vertices must be unique except for an optional closing point.")
        if _has_self_intersection(points):
            raise ValueError("Path2D requires a simple polygon without self-intersections.")
        if abs(_signed_area(points)) <= 1.0e-9:
            raise ValueError("Path2D requires a non-zero enclosed area.")

        object.__setattr__(self, "points", points)
        object.__setattr__(self, "_triangles", _triangulate_polygon(points))

    @classmethod
    def polygon(cls, *points: Point) -> Path2D:
        return cls(tuple(points))

    @property
    def bounds(self) -> Rect:
        xs = [point.x for point in self.points]
        ys = [point.y for point in self.points]
        left = min(xs)
        top = min(ys)
        return Rect(left, top, max(xs) - left, max(ys) - top)

    @property
    def triangle_count(self) -> int:
        return len(self._triangles)

    def contains(self, point: Point) -> bool:
        """Return whether ``point`` lies inside or on the polygon boundary."""

        inside = False
        points = self.points
        for index, current in enumerate(points):
            previous = points[index - 1]
            if _point_on_segment(point, previous, current):
                return True
            intersects = (current.y > point.y) != (previous.y > point.y)
            if not intersects:
                continue
            denominator = previous.y - current.y
            crossing_x = (
                (previous.x - current.x) * (point.y - current.y) / denominator + current.x
            )
            if point.x < crossing_x:
                inside = not inside
        return inside

    def triangulate(self) -> tuple[Triangle, ...]:
        """Return the immutable triangle cache prepared during path construction."""

        return self._triangles


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


def _signed_area(points: tuple[Point, ...]) -> float:
    return 0.5 * sum(
        point.x * points[(index + 1) % len(points)].y
        - points[(index + 1) % len(points)].x * point.y
        for index, point in enumerate(points)
    )


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _point_in_triangle(point: Point, a: Point, b: Point, c: Point, epsilon: float) -> bool:
    first = _cross(a, b, point)
    second = _cross(b, c, point)
    third = _cross(c, a, point)
    has_negative = first < -epsilon or second < -epsilon or third < -epsilon
    has_positive = first > epsilon or second > epsilon or third > epsilon
    return not (has_negative and has_positive)


def _point_on_segment(point: Point, a: Point, b: Point) -> bool:
    epsilon = 1.0e-9
    if abs(_cross(a, b, point)) > epsilon:
        return False
    return (
        min(a.x, b.x) - epsilon <= point.x <= max(a.x, b.x) + epsilon
        and min(a.y, b.y) - epsilon <= point.y <= max(a.y, b.y) + epsilon
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    epsilon = 1.0e-9
    ab_c = _cross(a, b, c)
    ab_d = _cross(a, b, d)
    cd_a = _cross(c, d, a)
    cd_b = _cross(c, d, b)

    if ab_c * ab_d < -epsilon and cd_a * cd_b < -epsilon:
        return True
    return (
        (abs(ab_c) <= epsilon and _point_on_segment(c, a, b))
        or (abs(ab_d) <= epsilon and _point_on_segment(d, a, b))
        or (abs(cd_a) <= epsilon and _point_on_segment(a, c, d))
        or (abs(cd_b) <= epsilon and _point_on_segment(b, c, d))
    )


def _has_self_intersection(points: tuple[Point, ...]) -> bool:
    count = len(points)
    for first_index in range(count):
        first_next = (first_index + 1) % count
        for second_index in range(first_index + 1, count):
            second_next = (second_index + 1) % count
            second_edge = (second_index, second_next)
            if first_index in second_edge or first_next in second_edge:
                continue
            if _segments_intersect(
                points[first_index],
                points[first_next],
                points[second_index],
                points[second_next],
            ):
                return True
    return False


def _triangulate_polygon(points: tuple[Point, ...]) -> tuple[Triangle, ...]:
    counter_clockwise = _signed_area(points) > 0.0
    indices = list(range(len(points)))
    triangles: list[Triangle] = []
    epsilon = 1.0e-9

    while len(indices) > 3:
        ear_found = False
        for position, current_index in enumerate(indices):
            previous_index = indices[position - 1]
            next_index = indices[(position + 1) % len(indices)]
            a = points[previous_index]
            b = points[current_index]
            c = points[next_index]
            cross = _cross(a, b, c)
            if counter_clockwise:
                if cross <= epsilon:
                    continue
            elif cross >= -epsilon:
                continue

            if any(
                _point_in_triangle(points[candidate], a, b, c, epsilon)
                for candidate in indices
                if candidate not in (previous_index, current_index, next_index)
            ):
                continue

            triangles.append((a, b, c))
            del indices[position]
            ear_found = True
            break

        if not ear_found:
            raise ValueError("Path2D could not be tessellated deterministically.")

    a, b, c = (points[index] for index in indices)
    triangles.append((a, b, c))
    return tuple(triangles)
