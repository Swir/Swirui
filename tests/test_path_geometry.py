from math import isclose

import pytest

from swirui.rendering import Color, PathGeometry, Point, Rect, SceneNode, SceneNodeKind


def _triangle_area_sum(path: PathGeometry) -> float:
    return sum(abs(triangle.signed_area) for triangle in path.triangles())


def test_convex_path_tessellates_to_n_minus_two_triangles() -> None:
    path = PathGeometry.polygon(
        Point(10, 10),
        Point(110, 10),
        Point(110, 90),
        Point(10, 90),
    )

    triangles = path.triangles()

    assert len(triangles) == 2
    assert all(triangle.signed_area > 0.0 for triangle in triangles)
    assert isclose(_triangle_area_sum(path), abs(path.signed_area))
    assert path.bounds == Rect(10, 10, 100, 80)
    assert path.clockwise is False


def test_clockwise_path_is_normalized_to_counter_clockwise_triangles() -> None:
    path = PathGeometry.polygon(
        Point(10, 10),
        Point(10, 90),
        Point(110, 90),
        Point(110, 10),
    )

    assert path.clockwise is True
    assert all(triangle.signed_area > 0.0 for triangle in path.triangles())
    assert isclose(_triangle_area_sum(path), abs(path.signed_area))


def test_concave_path_tessellation_preserves_polygon_area() -> None:
    path = PathGeometry.polygon(
        Point(0, 0),
        Point(120, 0),
        Point(120, 40),
        Point(60, 20),
        Point(0, 40),
    )

    triangles = path.triangles()

    assert len(triangles) == 3
    assert all(triangle.signed_area > 0.0 for triangle in triangles)
    assert isclose(_triangle_area_sum(path), abs(path.signed_area))


def test_duplicate_terminal_point_is_normalized_for_closed_paths() -> None:
    origin = Point(0, 0)
    path = PathGeometry((origin, Point(80, 0), Point(40, 60), origin))

    assert len(path.points) == 3
    assert len(path.triangles()) == 1


def test_self_intersecting_polygon_is_rejected() -> None:
    with pytest.raises(ValueError, match="simple non-self-intersecting"):
        PathGeometry.polygon(
            Point(0, 0),
            Point(100, 100),
            Point(0, 100),
            Point(100, 0),
        )


def test_degenerate_and_non_finite_paths_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-zero area"):
        PathGeometry.polygon(Point(0, 0), Point(50, 0), Point(100, 0))
    with pytest.raises(ValueError, match="finite"):
        PathGeometry.polygon(Point(0, 0), Point(float("inf"), 0), Point(0, 10))
    with pytest.raises(ValueError, match="consecutive duplicate"):
        PathGeometry.polygon(Point(0, 0), Point(50, 0), Point(50, 0), Point(0, 50))


def test_open_polyline_is_valid_but_not_fill_tessellatable() -> None:
    path = PathGeometry.polyline(Point(0, 0), Point(20, 10), Point(50, 5))

    assert path.closed is False
    assert path.signed_area == 0.0
    assert path.bounds == Rect(0, 0, 50, 10)
    with pytest.raises(ValueError, match="Open paths"):
        path.triangles()


def test_scene_path_node_requires_closed_filled_geometry() -> None:
    polygon = PathGeometry.polygon(Point(10, 10), Point(90, 10), Point(50, 70))
    node = SceneNode(
        key="triangle",
        kind=SceneNodeKind.PATH,
        bounds=polygon.bounds,
        fill=Color.from_hex("#00A8FF"),
        path=polygon,
    )

    assert node.path is polygon

    with pytest.raises(ValueError, match="require PathGeometry"):
        SceneNode(
            key="missing-path",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 10, 10),
            fill=Color.from_hex("#FFFFFF"),
        )
    with pytest.raises(ValueError, match="require a fill color"):
        SceneNode(
            key="missing-fill",
            kind=SceneNodeKind.PATH,
            bounds=polygon.bounds,
            path=polygon,
        )
    with pytest.raises(ValueError, match="require closed"):
        SceneNode(
            key="open",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 50, 20),
            fill=Color.from_hex("#FFFFFF"),
            path=PathGeometry.polyline(Point(0, 0), Point(50, 20)),
        )
