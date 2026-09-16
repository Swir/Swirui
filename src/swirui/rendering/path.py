"""Backend-neutral vector path geometry and deterministic polygon tessellation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .geometry import Point, Rect

_EPSILON = 1.0e-7


@dataclass(frozen=True, slots=True)
class Triangle:
    """A single filled triangle emitted by path tessellation."""

    a: Point
    b: Point
    c: Point

    @property
    def signed_area(self) -> float:
        return _cross(self.a, self.b, self.c) * 0.5


@dataclass(frozen=True, slots=True)
class PathGeometry:
    """Immutable polyline/polygon geometry authored in logical device-independent pixels.

    Closed paths represent filled simple polygons and can be tessellated into GPU-friendly
    triangles with :meth:`triangles`. Open paths are retained for the future stroke pipeline
    and require at least two points.
    """

    points: tuple[Point, ...]
    closed: bool = True

    def __post_init__(self) -> None:
        points = _normalized_points(self.points, self.closed)
        object.__setattr__(self, "points", points)
        required = 3 if self.closed else 2
        if len(points) < required:
            noun = "Closed paths" if self.closed else "Open paths"
            raise ValueError(f"{noun} require at least {required} distinct points.")
        if any(not isfinite(value) for point in points for value in (point.x, point.y)):
            raise ValueError("Path coordinates must be finite.")
        if any(points[index] == points[index + 1] for index in range(len(points) - 1)):
            raise ValueError("Path cannot contain consecutive duplicate points.")
        if self.closed:
            if abs(self.signed_area) <= _EPSILON:
                raise ValueError("Closed path must enclose a non-zero area.")
            if not _is_simple_polygon(points):
                raise ValueError("Closed path must be a simple non-self-intersecting polygon.")

    @classmethod
    def polygon(cls, *points: Point) -> PathGeometry:
        """Create a closed polygon path from positional points."""

        return cls(tuple(points), closed=True)

    @classmethod
    def polyline(cls, *points: Point) -> PathGeometry:
        """Create an open polyline retained for future stroke rendering."""

        return cls(tuple(points), closed=False)

    @property
    def bounds(self) -> Rect:
        xs = [point.x for point in self.points]
        ys = [point.y for point in self.points]
        left = min(xs)
        top = min(ys)
        return Rect(left, top, max(xs) - left, max(ys) - top)

    @property
    def signed_area(self) -> float:
        if not self.closed:
            return 0.0
        total = 0.0
        for index, point in enumerate(self.points):
            following = self.points[(index + 1) % len(self.points)]
            total += point.x * following.y - following.x * point.y
        return total * 0.5

    @property
    def clockwise(self) -> bool:
        return self.signed_area < 0.0

    def triangles(self) -> tuple[Triangle, ...]:
        """Tessellate a simple closed polygon using deterministic ear clipping.

        The returned triangles always use counter-clockwise winding regardless of the input
        polygon winding. Concave polygons are supported. Self-intersecting and degenerate
        polygons are rejected during construction instead of producing undefined geometry.
        """

        if not self.closed:
            raise ValueError("Open paths cannot be tessellated as filled geometry.")
        return _triangulate(self.points)


def _normalized_points(points: tuple[Point, ...], closed: bool) -> tuple[Point, ...]:
    normalized = tuple(points)
    if closed and len(normalized) >= 2 and normalized[0] == normalized[-1]:
        normalized = normalized[:-1]
    return normalized


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _orientation(a: Point, b: Point, c: Point) -> int:
    value = _cross(a, b, c)
    if abs(value) <= _EPSILON:
        return 0
    return 1 if value > 0.0 else -1


def _on_segment(a: Point, b: Point, point: Point) -> bool:
    return (
        min(a.x, b.x) - _EPSILON <= point.x <= max(a.x, b.x) + _EPSILON
        and min(a.y, b.y) - _EPSILON <= point.y <= max(a.y, b.y) + _EPSILON
        and abs(_cross(a, b, point)) <= _EPSILON
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(a, b, c):
        return True
    if o2 == 0 and _on_segment(a, b, d):
        return True
    if o3 == 0 and _on_segment(c, d, a):
        return True
    if o4 == 0 and _on_segment(c, d, b):
        return True
    return False


def _is_simple_polygon(points: tuple[Point, ...]) -> bool:
    count = len(points)
    for first in range(count):
        a = points[first]
        b = points[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first:
                continue
            if second == (first + 1) % count:
                continue
            if first == (second + 1) % count:
                continue
            c = points[second]
            d = points[(second + 1) % count]
            if _segments_intersect(a, b, c, d):
                return False
    return True


def _point_in_triangle(point: Point, a: Point, b: Point, c: Point) -> bool:
    c1 = _cross(a, b, point)
    c2 = _cross(b, c, point)
    c3 = _cross(c, a, point)
    has_negative = c1 < -_EPSILON or c2 < -_EPSILON or c3 < -_EPSILON
    has_positive = c1 > _EPSILON or c2 > _EPSILON or c3 > _EPSILON
    return not (has_negative and has_positive)


def _triangulate(points: tuple[Point, ...]) -> tuple[Triangle, ...]:
    if len(points) == 3:
        a, b, c = points
        if _cross(a, b, c) < 0.0:
            b, c = c, b
        return (Triangle(a, b, c),)

    indices = list(range(len(points)))
    if _polygon_signed_area(points) < 0.0:
        indices.reverse()

    triangles: list[Triangle] = []
    maximum_iterations = len(points) * len(points)
    iterations = 0
    while len(indices) > 3:
        ear_found = False
        for cursor, current_index in enumerate(indices):
            previous_index = indices[cursor - 1]
            next_index = indices[(cursor + 1) % len(indices)]
            a = points[previous_index]
            b = points[current_index]
            c = points[next_index]
            if _cross(a, b, c) <= _EPSILON:
                continue
            if any(
                _point_in_triangle(points[candidate], a, b, c)
                for candidate in indices
                if candidate not in (previous_index, current_index, next_index)
            ):
                continue
            triangles.append(Triangle(a, b, c))
            del indices[cursor]
            ear_found = True
            break
        iterations += 1
        if not ear_found or iterations > maximum_iterations:
            raise ValueError("Path tessellation failed; polygon may be degenerate.")

    a, b, c = (points[index] for index in indices)
    if _cross(a, b, c) <= _EPSILON:
        raise ValueError("Path tessellation produced a degenerate final triangle.")
    triangles.append(Triangle(a, b, c))
    return tuple(triangles)


def _polygon_signed_area(points: tuple[Point, ...]) -> float:
    total = 0.0
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        total += point.x * following.y - following.x * point.y
    return total * 0.5
