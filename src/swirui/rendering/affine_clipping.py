"""Exact convex clipping helpers for retained affine GPU geometry."""

from __future__ import annotations

from collections.abc import Sequence

from .affine import Affine2D
from .geometry import Point, Rect

_EPSILON = 1.0e-9
ConvexPolygon = tuple[Point, ...]
Triangle = tuple[Point, Point, Point]


def transformed_rect_polygon(transform: Affine2D, bounds: Rect) -> ConvexPolygon:
    """Return the exact world-space quad for ``bounds`` under ``transform``."""
    return (
        transform.transform_point(Point(bounds.x, bounds.y)),
        transform.transform_point(Point(bounds.right, bounds.y)),
        transform.transform_point(Point(bounds.right, bounds.bottom)),
        transform.transform_point(Point(bounds.x, bounds.bottom)),
    )


def clip_triangle_to_convex_polygons(
    triangle: Triangle,
    clips: Sequence[ConvexPolygon],
) -> ConvexPolygon:
    """Clip a triangle against ordered convex clip polygons."""
    subject: ConvexPolygon = triangle
    for clip in clips:
        subject = clip_convex_polygon(subject, clip)
        if len(subject) < 3:
            return ()
    return subject


def clip_convex_polygon(
    subject: Sequence[Point],
    clip: Sequence[Point],
) -> ConvexPolygon:
    """Sutherland-Hodgman clipping independent of polygon winding."""
    if len(subject) < 3 or len(clip) < 3:
        return ()
    orientation = 1.0 if _signed_area(clip) >= 0.0 else -1.0
    output = tuple(subject)
    for index, clip_start in enumerate(clip):
        clip_end = clip[(index + 1) % len(clip)]
        if not output:
            return ()
        input_vertices = output
        clipped: list[Point] = []
        previous = input_vertices[-1]
        previous_inside = _inside(previous, clip_start, clip_end, orientation)
        for current in input_vertices:
            current_inside = _inside(current, clip_start, clip_end, orientation)
            if current_inside:
                if not previous_inside:
                    clipped.append(
                        _intersection(previous, current, clip_start, clip_end)
                    )
                clipped.append(current)
            elif previous_inside:
                clipped.append(_intersection(previous, current, clip_start, clip_end))
            previous = current
            previous_inside = current_inside
        output = _deduplicate(clipped)
    if len(output) < 3 or abs(_signed_area(output)) <= _EPSILON:
        return ()
    return output


def triangulate_convex_polygon(polygon: Sequence[Point]) -> tuple[Triangle, ...]:
    """Triangulate a convex polygon as a deterministic fan."""
    if len(polygon) < 3:
        return ()
    anchor = polygon[0]
    result: list[Triangle] = []
    for index in range(1, len(polygon) - 1):
        triangle = (anchor, polygon[index], polygon[index + 1])
        if abs(_signed_area(triangle)) > _EPSILON:
            result.append(triangle)
    return tuple(result)


def point_in_convex_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Return whether ``point`` lies inside or on a convex polygon boundary."""
    if len(polygon) < 3:
        return False
    orientation = 1.0 if _signed_area(polygon) >= 0.0 else -1.0
    return all(
        _inside(point, polygon[index], polygon[(index + 1) % len(polygon)], orientation)
        for index in range(len(polygon))
    )


def _inside(point: Point, start: Point, end: Point, orientation: float) -> bool:
    return orientation * _cross(start, end, point) >= -_EPSILON


def _cross(start: Point, end: Point, point: Point) -> float:
    return (end.x - start.x) * (point.y - start.y) - (end.y - start.y) * (
        point.x - start.x
    )


def _intersection(
    segment_start: Point,
    segment_end: Point,
    line_start: Point,
    line_end: Point,
) -> Point:
    segment_x = segment_end.x - segment_start.x
    segment_y = segment_end.y - segment_start.y
    line_x = line_end.x - line_start.x
    line_y = line_end.y - line_start.y
    denominator = segment_x * line_y - segment_y * line_x
    if abs(denominator) <= _EPSILON:
        return segment_end
    offset_x = line_start.x - segment_start.x
    offset_y = line_start.y - segment_start.y
    parameter = (offset_x * line_y - offset_y * line_x) / denominator
    parameter = min(1.0, max(0.0, parameter))
    return Point(
        segment_start.x + parameter * segment_x,
        segment_start.y + parameter * segment_y,
    )


def _signed_area(points: Sequence[Point]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        area += point.x * following.y - following.x * point.y
    return area * 0.5


def _deduplicate(points: Sequence[Point]) -> ConvexPolygon:
    result: list[Point] = []
    for point in points:
        if not result or not _close(result[-1], point):
            result.append(point)
    if len(result) > 1 and _close(result[0], result[-1]):
        result.pop()
    return tuple(result)


def _close(left: Point, right: Point) -> bool:
    return abs(left.x - right.x) <= _EPSILON and abs(left.y - right.y) <= _EPSILON
