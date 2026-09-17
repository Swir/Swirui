import math

import pytest

from swirui import Window
from swirui.rendering import (
    Color,
    Parallax,
    PerspectivePlane,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def test_perspective_plane_identity_preserves_bounds_and_quad() -> None:
    bounds = Rect(100.0, 80.0, 320.0, 180.0)
    plane = PerspectivePlane()

    corners = plane.projected_corners(bounds)
    projected_bounds, path = plane.projected_path(bounds)

    assert corners == (
        Point(100.0, 80.0),
        Point(420.0, 80.0),
        Point(420.0, 260.0),
        Point(100.0, 260.0),
    )
    assert projected_bounds == bounds
    assert path.points == (
        Point(0.0, 0.0),
        Point(320.0, 0.0),
        Point(320.0, 180.0),
        Point(0.0, 180.0),
    )
    assert path.triangle_count == 2


def test_perspective_plane_tilt_builds_finite_trapezoid() -> None:
    bounds = Rect(60.0, 70.0, 360.0, 220.0)
    corners = PerspectivePlane(
        rotation_x_degrees=14.0,
        rotation_y_degrees=-18.0,
        perspective=760.0,
    ).projected_corners(bounds)

    assert corners != (
        Point(bounds.x, bounds.y),
        Point(bounds.right, bounds.y),
        Point(bounds.right, bounds.bottom),
        Point(bounds.x, bounds.bottom),
    )
    assert all(math.isfinite(value) for point in corners for value in (point.x, point.y))
    top_width = math.dist((corners[0].x, corners[0].y), (corners[1].x, corners[1].y))
    bottom_width = math.dist((corners[3].x, corners[3].y), (corners[2].x, corners[2].y))
    assert top_width != pytest.approx(bottom_width)


def test_perspective_depth_moves_surface_toward_camera() -> None:
    bounds = Rect(100.0, 100.0, 240.0, 140.0)
    base_bounds, _ = PerspectivePlane(perspective=900.0).projected_path(bounds)
    raised_bounds, _ = PerspectivePlane(perspective=900.0, depth=180.0).projected_path(bounds)

    assert raised_bounds.width > base_bounds.width
    assert raised_bounds.height > base_bounds.height


def test_perspective_plane_validates_geometry_and_camera_crossing() -> None:
    with pytest.raises(ValueError, match="rotation_x_degrees"):
        PerspectivePlane(rotation_x_degrees=81.0)
    with pytest.raises(ValueError, match="rotation_y_degrees"):
        PerspectivePlane(rotation_y_degrees=-81.0)
    with pytest.raises(ValueError, match="perspective"):
        PerspectivePlane(perspective=0.0)
    with pytest.raises(ValueError, match="origin"):
        PerspectivePlane(origin=Point(-0.1, 0.5))
    with pytest.raises(ValueError, match="finite"):
        PerspectivePlane(depth=math.inf)
    with pytest.raises(ValueError, match="positive dimensions"):
        PerspectivePlane().projected_corners(Rect(0.0, 0.0, 0.0, 40.0))
    with pytest.raises(ValueError, match="camera plane"):
        PerspectivePlane(
            rotation_y_degrees=60.0,
            perspective=40.0,
            depth=30.0,
        ).projected_corners(Rect(0.0, 0.0, 200.0, 80.0))


def test_perspective_scene_node_uses_projected_path_for_hit_testing() -> None:
    node = PerspectivePlane(
        rotation_x_degrees=12.0,
        rotation_y_degrees=16.0,
        perspective=820.0,
    ).to_scene_node(
        "tilted-card",
        Rect(90.0, 70.0, 260.0, 160.0),
        fill=Color.from_hex("#176BFF"),
    )

    assert node.kind is SceneNodeKind.PATH
    assert node.path is not None
    assert node.path.triangle_count == 2
    assert node.hit_test(Point(220.0, 150.0)) is node
    assert node.hit_testable


def test_parallax_resolves_center_and_viewport_extremes() -> None:
    viewport = Rect(0.0, 0.0, 800.0, 600.0)
    parallax = Parallax(max_rotation_x_degrees=10.0, max_rotation_y_degrees=14.0)

    center = parallax.resolve(Point(400.0, 300.0), viewport)
    top_right = parallax.resolve(Point(800.0, 0.0), viewport)

    assert center.rotation_x_degrees == pytest.approx(0.0)
    assert center.rotation_y_degrees == pytest.approx(0.0)
    assert top_right.rotation_x_degrees == pytest.approx(10.0)
    assert top_right.rotation_y_degrees == pytest.approx(14.0)


def test_parallax_clamps_pointer_outside_viewport() -> None:
    viewport = Rect(100.0, 50.0, 400.0, 300.0)
    parallax = Parallax(max_rotation_x_degrees=9.0, max_rotation_y_degrees=11.0)

    clamped = parallax.resolve(Point(10_000.0, -10_000.0), viewport)
    edge = parallax.resolve(Point(viewport.right, viewport.y), viewport)

    assert clamped == edge


def test_parallax_validates_budget_and_viewport() -> None:
    with pytest.raises(ValueError, match="max_rotation_x_degrees"):
        Parallax(max_rotation_x_degrees=-1.0)
    with pytest.raises(ValueError, match="max_rotation_y_degrees"):
        Parallax(max_rotation_y_degrees=81.0)
    with pytest.raises(ValueError, match="finite"):
        Parallax(max_rotation_x_degrees=math.nan)
    with pytest.raises(ValueError, match="positive dimensions"):
        Parallax().resolve(Point(), Rect(0.0, 0.0, 0.0, 100.0))


def test_parallax_flows_into_existing_wgpu_path_batch() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 640.0, 420.0))
    root.add(
        Parallax(max_rotation_x_degrees=9.0, max_rotation_y_degrees=13.0).to_scene_node(
            "parallax-card",
            Rect(150.0, 100.0, 340.0, 210.0),
            pointer=Point(580.0, 60.0),
            viewport=Rect(0.0, 0.0, 640.0, 420.0),
            fill=Color.from_hex("#0EA5E9"),
        )
    )
    window = Window(width=640, height=420)
    window.set_scene(Scene(640.0, 420.0, root))

    vertices = WgpuRenderer()._path_vertices(window)

    assert len(vertices) == 6
    assert all(len(vertex) == 10 for vertex in vertices)
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
