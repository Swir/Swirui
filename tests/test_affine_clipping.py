from __future__ import annotations

import math

import pytest

from swirui.rendering.affine import Affine2D
from swirui.rendering.affine_clipping import (
    clip_convex_polygon,
    clip_triangle_to_convex_polygons,
    point_in_convex_polygon,
    transformed_rect_polygon,
    triangulate_convex_polygon,
)
from swirui.rendering.geometry import Point, Rect


def _polygon_area(points: tuple[Point, ...]) -> float:
    return abs(
        sum(
            point.x * points[(index + 1) % len(points)].y
            - points[(index + 1) % len(points)].x * point.y
            for index, point in enumerate(points)
        )
        * 0.5
    )


def test_rotated_rect_polygon_preserves_exact_corners() -> None:
    bounds = Rect(20.0, 30.0, 100.0, 60.0)
    transform = Affine2D.rotation(math.radians(30.0), origin=Point(70.0, 60.0))

    polygon = transformed_rect_polygon(transform, bounds)

    assert len(polygon) == 4
    expected = (
        transform.transform_point(Point(20.0, 30.0)),
        transform.transform_point(Point(120.0, 30.0)),
        transform.transform_point(Point(120.0, 90.0)),
        transform.transform_point(Point(20.0, 90.0)),
    )
    for point, expected_point in zip(polygon, expected, strict=True):
        assert point.x == pytest.approx(expected_point.x)
        assert point.y == pytest.approx(expected_point.y)


def test_triangle_clipping_handles_nested_rotated_and_sheared_regions() -> None:
    outer = transformed_rect_polygon(
        Affine2D.rotation(math.radians(18.0), origin=Point(150.0, 120.0)),
        Rect(40.0, 35.0, 220.0, 170.0),
    )
    inner = transformed_rect_polygon(
        Affine2D(1.0, 0.18, -0.24, 1.0, 18.0, -6.0),
        Rect(75.0, 65.0, 145.0, 105.0),
    )
    triangle = (
        Point(20.0, 35.0),
        Point(300.0, 55.0),
        Point(145.0, 250.0),
    )

    clipped = clip_triangle_to_convex_polygons(triangle, (outer, inner))

    assert len(clipped) >= 3
    assert all(point_in_convex_polygon(point, outer) for point in clipped)
    assert all(point_in_convex_polygon(point, inner) for point in clipped)
    assert _polygon_area(clipped) > 0.0


def test_clipping_is_winding_independent_for_reflected_clip() -> None:
    subject = (
        Point(0.0, 0.0),
        Point(160.0, 0.0),
        Point(160.0, 120.0),
        Point(0.0, 120.0),
    )
    reflected = transformed_rect_polygon(
        Affine2D(-1.0, 0.0, 0.0, 1.0, 140.0, 0.0),
        Rect(20.0, 20.0, 90.0, 70.0),
    )

    clipped = clip_convex_polygon(subject, reflected)

    assert len(clipped) == 4
    assert _polygon_area(clipped) == pytest.approx(90.0 * 70.0)
    assert all(point_in_convex_polygon(point, reflected) for point in clipped)


def test_convex_fan_triangulation_preserves_clipped_area() -> None:
    polygon = (
        Point(10.0, 10.0),
        Point(90.0, 5.0),
        Point(120.0, 50.0),
        Point(75.0, 95.0),
        Point(20.0, 80.0),
    )

    triangles = triangulate_convex_polygon(polygon)

    assert len(triangles) == 3
    assert sum(_polygon_area(triangle) for triangle in triangles) == pytest.approx(
        _polygon_area(polygon)
    )


def test_fully_outside_triangle_is_removed() -> None:
    clip = (
        Point(100.0, 100.0),
        Point(200.0, 100.0),
        Point(200.0, 200.0),
        Point(100.0, 200.0),
    )
    triangle = (Point(0.0, 0.0), Point(20.0, 0.0), Point(0.0, 20.0))

    assert clip_triangle_to_convex_polygons(triangle, (clip,)) == ()
