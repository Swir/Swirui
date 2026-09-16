import pytest

from swirui.rendering import Color, Path2D, Point, Rect, SceneNode, SceneNodeKind


def test_path2d_triangulates_convex_and_concave_polygons() -> None:
    triangle = Path2D.polygon(Point(0, 0), Point(100, 0), Point(20, 80))
    assert len(triangle.triangulate()) == 1

    concave = Path2D.polygon(
        Point(0, 0),
        Point(120, 0),
        Point(120, 40),
        Point(50, 40),
        Point(50, 120),
        Point(0, 120),
    )
    triangles = concave.triangulate()
    assert len(triangles) == 4
    assert sum(abs(_triangle_area(*item)) for item in triangles) == pytest.approx(8800.0)


def test_path2d_accepts_explicit_closing_point_and_reports_bounds() -> None:
    path = Path2D(
        (
            Point(5, 10),
            Point(45, 10),
            Point(25, 60),
            Point(5, 10),
        )
    )
    assert len(path.points) == 3
    assert path.bounds == Rect(5, 10, 40, 50)


def test_path2d_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="at least three"):
        Path2D.polygon(Point(0, 0), Point(10, 0))
    with pytest.raises(ValueError, match="unique"):
        Path2D.polygon(Point(0, 0), Point(10, 0), Point(10, 0), Point(0, 10))
    with pytest.raises(ValueError, match="non-zero"):
        Path2D.polygon(Point(0, 0), Point(10, 10), Point(20, 20))


def test_path2d_contains_inside_boundary_and_outside_points() -> None:
    path = Path2D.polygon(
        Point(0, 0),
        Point(100, 0),
        Point(100, 35),
        Point(35, 35),
        Point(35, 100),
        Point(0, 100),
    )
    assert path.contains(Point(15, 80))
    assert path.contains(Point(35, 70))
    assert not path.contains(Point(80, 80))


def test_scene_path_hit_testing_uses_polygon_not_only_bounds() -> None:
    node = SceneNode(
        key="triangle",
        kind=SceneNodeKind.PATH,
        bounds=Rect(100, 100, 100, 100),
        fill=Color.from_hex("#008CFF"),
        path=Path2D.polygon(Point(0, 0), Point(100, 0), Point(0, 100)),
    )
    assert node.hit_test(Point(120, 120)) is node
    assert node.hit_test(Point(190, 190)) is None


def test_scene_path_requires_geometry_and_fill() -> None:
    path = Path2D.polygon(Point(0, 0), Point(100, 0), Point(0, 100))
    with pytest.raises(ValueError, match="Path2D"):
        SceneNode(
            key="missing-path",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 100, 100),
            fill=Color.from_hex("#008CFF"),
        )
    with pytest.raises(ValueError, match="fill"):
        SceneNode(
            key="missing-fill",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 100, 100),
            path=path,
        )


def _triangle_area(a: Point, b: Point, c: Point) -> float:
    return ((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) / 2.0
