from __future__ import annotations

import math

import pytest

from swirui.rendering import Color, Path2D, Point, Rect, SceneNode, SceneNodeKind


def _triangle_area(a: Point, b: Point, c: Point) -> float:
    return abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * 0.5


def test_polygon_path_reports_bounds_and_contains_boundary_points() -> None:
    path = Path2D.polygon([(10, 20), (80, 20), (80, 70), (10, 70)])

    assert path.closed
    assert path.bounds == Rect(10.0, 20.0, 70.0, 50.0)
    assert path.contains(Point(40, 40))
    assert path.contains(Point(10, 45))
    assert not path.contains(Point(9, 45))


def test_concave_path_triangulates_without_losing_area() -> None:
    path = Path2D.polygon([(0, 0), (6, 0), (6, 6), (3, 3), (0, 6)])

    triangles = path.triangulate()

    assert len(triangles) == 3
    tessellated_area = sum(_triangle_area(*triangle) for triangle in triangles)
    assert tessellated_area == pytest.approx(27.0)


def test_clockwise_polygon_triangulates_deterministically() -> None:
    path = Path2D.polygon([(0, 0), (0, 4), (4, 4), (4, 0)])

    first = path.triangulate()
    second = path.triangulate()

    assert first == second
    assert len(first) == 2
    assert sum(_triangle_area(*triangle) for triangle in first) == pytest.approx(16.0)


def test_self_intersecting_polygon_is_rejected_by_tessellator() -> None:
    path = Path2D.polygon([(0, 0), (4, 4), (0, 4), (4, 0)])

    with pytest.raises(ValueError, match="Self-intersecting"):
        path.triangulate()


def test_path_builder_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="line_to requires"):
        Path2D().line_to(1, 1)

    with pytest.raises(ValueError, match="finite"):
        Path2D().move_to(math.inf, 0)

    with pytest.raises(ValueError, match="at least three"):
        Path2D().move_to(0, 0).line_to(1, 0).close()


def test_path_scene_node_uses_polygon_for_hit_testing() -> None:
    path = Path2D.polygon([(0, 0), (100, 0), (0, 100)])
    node = SceneNode(
        key="triangle",
        kind=SceneNodeKind.PATH,
        bounds=Rect(0, 0, 100, 100),
        fill=Color.from_hex("#00AAFF"),
        path=path,
    )

    assert node.hit_test(Point(20, 20)) is node
    assert node.hit_test(Point(90, 90)) is None


def test_path_scene_node_requires_closed_filled_path_inside_bounds() -> None:
    open_path = Path2D().move_to(0, 0).line_to(10, 0).line_to(0, 10)
    with pytest.raises(ValueError, match="closed Path2D"):
        SceneNode(
            key="open",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 10, 10),
            fill=Color(1, 1, 1, 1),
            path=open_path,
        )

    closed_path = open_path.close()
    with pytest.raises(ValueError, match="fill color"):
        SceneNode(
            key="no-fill",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 10, 10),
            path=closed_path,
        )

    with pytest.raises(ValueError, match="must contain"):
        SceneNode(
            key="too-small",
            kind=SceneNodeKind.PATH,
            bounds=Rect(0, 0, 5, 5),
            fill=Color(1, 1, 1, 1),
            path=closed_path,
        )
