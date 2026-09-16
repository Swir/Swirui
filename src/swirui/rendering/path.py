"""Backend-neutral path geometry and deterministic polygon tessellation."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from .geometry import Point, Rect

Triangle = tuple[Point, Point, Point]
_EPSILON = 1.0e-9


@dataclass(slots=True)
class Path2D:
    """A simple closed 2D path prepared for renderer tessellation.

    The 0.2 renderer foundation intentionally starts with one polygonal contour:
    ``move_to`` + ``line_to`` + ``close``. Curves and multiple contours can be
    layered on top without changing the scene-node contract. ``triangulate`` uses
    deterministic ear clipping so renderer backends receive backend-neutral
    triangles rather than owning shape topology logic themselves.
    """

    _points: list[Point] = field(default_factory=list)
    _closed: bool = False

    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(self._points)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def bounds(self) -> Rect:
        if not self._points:
            return Rect(0.0, 0.0, 0.0, 0.0)
        min_x = min(point.x for point in self._points)
        min_y = min(point.y for point in self._points)
        max_x = max(point.x for point in self._points)
        max_y = max(point.y for point in self._points)
        return Rect(min_x, min_y, max_x - min_x, max_y - min_y)

    def move_to(self, x: float, y: float) -> Path2D:
        """Start the single contour used by the current path foundation."""

        if self._points:
            raise ValueError("Path2D currently supports one contour; move_to can be used once.")
        self._points.append(_point(x, y))
        return self

    def line_to(self, x: float, y: float) -> Path2D:
        if not self._points:
            raise ValueError("line_to requires an initial move_to point.")
        if self._closed:
            raise ValueError("Cannot append points after a Path2D has been closed.")
        point = _point(x, y)
        if point == self._points[-1]:
            raise ValueError("Consecutive path points must be distinct.")
        self._points.append(point)
        return self

    def close(self) -> Path2D:
        if self._closed:
            return self
        if len(self._points) < 3:
            raise ValueError("A closed Path2D requires at least three points.")
        if self._points[0] == self._points[-1]:
            self._points.pop()
        if len(self._points) < 3:
            raise ValueError("A closed Path2D requires at least three distinct points.")
        self._closed = True
        return self

    @classmethod
    def polygon(cls, points: Iterable[Point | tuple[float, float]]) -> Path2D:
        prepared: list[Point] = []
        for value in points:
            if isinstance(value, Point):
                prepared.append(_point(value.x, value.y))
            else:
                x, y = value
                prepared.append(_point(x, y))
        if len(prepared) < 3:
            raise ValueError("A polygon Path2D requires at least three points.")
        path = cls().move_to(prepared[0].x, prepared[0].y)
        for point in prepared[1:]:
            path.line_to(point.x, point.y)
        return path.close()

    def contains(self, point: Point) -> bool:
        """Return whether ``point`` is inside or on the boundary of this path."""

        if not self._closed or len(self._points) < 3:
            return False
        if not self.bounds.contains(point):
            return False

        inside = False
        previous = self._points[-1]
        for current in self._points:
            if _point_on_segment(point, previous, current):
                return True
            if (current.y > point.y) != (previous.y > point.y):
                crossing_x = (
                    (previous.x - current.x)
                    * (point.y - current.y)
                    / (previous.y - current.y)
                    + current.x
                )
                if point.x < crossing_x:
                    inside = not inside
            previous = current
        return inside

    def triangulate(self) -> tuple[Triangle, ...]:
        """Triangulate a simple closed polygon using deterministic ear clipping."""

        if not self._closed:
            raise ValueError("Path2D must be closed before triangulation.")
        points = self._points
        if len(points) < 3:
            raise ValueError("Path2D requires at least three points for triangulation.")
        if _has_self_intersection(points):
            raise ValueError("Self-intersecting Path2D polygons are not supported.")

        area = _signed_area(points)
        if abs(area) <= _EPSILON:
            raise ValueError("Path2D polygon area must be greater than zero.")

        indices = list(range(len(points)))
        if area < 0.0:
            indices.reverse()

        triangles: list[Triangle] = []
        while len(indices) > 3:
            ear_index = _find_ear(points, indices)
            if ear_index is None:
                raise ValueError("Path2D polygon could not be triangulated deterministically.")
            previous = indices[(ear_index - 1) % len(indices)]
            current = indices[ear_index]
            following = indices[(ear_index + 1) % len(indices)]
            triangles.append((points[previous], points[current], points[following]))
            del indices[ear_index]

        triangles.append((points[indices[0]], points[indices[1]], points[indices[2]]))
        return tuple(triangles)


def _point(x: float, y: float) -> Point:
    x_value = float(x)
    y_value = float(y)
    if not math.isfinite(x_value) or not math.isfinite(y_value):
        raise ValueError("Path2D coordinates must be finite.")
    return Point(x_value, y_value)


def _signed_area(points: list[Point]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        area += point.x * following.y - following.x * point.y
    return area * 0.5


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _find_ear(points: list[Point], indices: list[int]) -> int | None:
    for position, current in enumerate(indices):
        previous = indices[(position - 1) % len(indices)]
        following = indices[(position + 1) % len(indices)]
        a, b, c = points[previous], points[current], points[following]
        if _cross(a, b, c) <= _EPSILON:
            continue
        if any(
            candidate not in (previous, current, following)
            and _point_in_triangle(points[candidate], a, b, c)
            for candidate in indices
        ):
            continue
        return position
    return None


def _point_in_triangle(point: Point, a: Point, b: Point, c: Point) -> bool:
    ab = _cross(a, b, point)
    bc = _cross(b, c, point)
    ca = _cross(c, a, point)
    return ab >= -_EPSILON and bc >= -_EPSILON and ca >= -_EPSILON


def _point_on_segment(point: Point, a: Point, b: Point) -> bool:
    if abs(_cross(a, b, point)) > _EPSILON:
        return False
    return (
        min(a.x, b.x) - _EPSILON <= point.x <= max(a.x, b.x) + _EPSILON
        and min(a.y, b.y) - _EPSILON <= point.y <= max(a.y, b.y) + _EPSILON
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab_c = _cross(a, b, c)
    ab_d = _cross(a, b, d)
    cd_a = _cross(c, d, a)
    cd_b = _cross(c, d, b)

    if ab_c * ab_d < -_EPSILON and cd_a * cd_b < -_EPSILON:
        return True
    return (
        (abs(ab_c) <= _EPSILON and _point_on_segment(c, a, b))
        or (abs(ab_d) <= _EPSILON and _point_on_segment(d, a, b))
        or (abs(cd_a) <= _EPSILON and _point_on_segment(a, c, d))
        or (abs(cd_b) <= _EPSILON and _point_on_segment(b, c, d))
    )


def _has_self_intersection(points: list[Point]) -> bool:
    count = len(points)
    for first in range(count):
        first_next = (first + 1) % count
        for second in range(first + 1, count):
            second_next = (second + 1) % count
            if first in (second, second_next) or first_next in (second, second_next):
                continue
            if _segments_intersect(
                points[first],
                points[first_next],
                points[second],
                points[second_next],
            ):
                return True
    return False
