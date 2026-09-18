from __future__ import annotations

import math

import pytest

from swirui.rendering import Color, Path2D, Point, Rect, Scene, SceneNode, SceneNodeKind
from swirui.rendering.affine import Affine2D


def test_rotation_inverse_and_composition_are_deterministic() -> None:
    origin = Point(50.0, 40.0)
    rotation = Affine2D.rotation(math.pi / 2.0, origin=origin)
    translated = rotation.then(Affine2D.translation(12.0, -8.0))

    point = Point(70.0, 40.0)
    rotated = rotation.transform_point(point)
    assert rotated.x == pytest.approx(50.0)
    assert rotated.y == pytest.approx(60.0)

    visual = translated.transform_point(point)
    restored = translated.inverse().transform_point(visual)
    assert restored.x == pytest.approx(point.x)
    assert restored.y == pytest.approx(point.y)


def test_affine_rect_bounds_enclose_rotated_geometry() -> None:
    rect = Rect(0.0, 0.0, 100.0, 50.0)
    transform = Affine2D.rotation(math.pi / 2.0, origin=Point(50.0, 25.0))

    bounds = transform.transform_rect_bounds(rect)

    assert bounds.x == pytest.approx(25.0)
    assert bounds.y == pytest.approx(-25.0)
    assert bounds.width == pytest.approx(50.0)
    assert bounds.height == pytest.approx(100.0)


def test_affine_validation_rejects_non_finite_and_singular_matrices() -> None:
    with pytest.raises(ValueError, match="finite"):
        Affine2D(tx=math.nan)
    with pytest.raises(ValueError, match="invertible"):
        Affine2D(m11=0.0, m22=0.0)
    with pytest.raises(ValueError, match="Rotation angle"):
        Affine2D.rotation(math.inf)
    with pytest.raises(ValueError, match="greater than zero"):
        Affine2D.uniform_scale(0.0)


def test_scene_hit_testing_inverts_rotated_rectangle_transform() -> None:
    node = SceneNode(
        key="rotated-card",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(20.0, 30.0, 120.0, 50.0),
        fill=Color.from_hex("#0088FF"),
        transform=Affine2D.rotation(math.radians(38.0), origin=Point(80.0, 55.0)),
    )
    scene = Scene(320.0, 240.0, node)
    authored_hit = Point(36.0, 46.0)
    visual_hit = node.transform.transform_point(authored_hit)

    assert scene.has_affine_transforms is True
    assert node.visual_bounds.contains(visual_hit)
    assert scene.hit_test(visual_hit) is node

    visual_aabb_corner = Point(node.visual_bounds.x + 0.1, node.visual_bounds.y + 0.1)
    assert node.visual_bounds.contains(visual_aabb_corner)
    assert scene.hit_test(visual_aabb_corner) is None


def test_rotated_path_hit_testing_preserves_local_polygon_geometry() -> None:
    path = Path2D.polygon(Point(0.0, 0.0), Point(80.0, 0.0), Point(0.0, 80.0))
    node = SceneNode(
        key="rotated-path",
        kind=SceneNodeKind.PATH,
        bounds=Rect(100.0, 80.0, 80.0, 80.0),
        fill=Color.from_hex("#62E5FF"),
        path=path,
        transform=Affine2D.rotation(math.radians(-27.0), origin=Point(140.0, 120.0)),
    )
    scene = Scene(360.0, 260.0, node)

    inside_visual = node.transform.transform_point(Point(115.0, 95.0))
    outside_visual = node.transform.transform_point(Point(165.0, 145.0))

    assert scene.hit_test(inside_visual) is node
    assert scene.hit_test(outside_visual) is None


def test_transformed_raster_composition_is_explicitly_gated() -> None:
    node = SceneNode(
        key="rotation-gate",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(10.0, 10.0, 90.0, 40.0),
        fill=Color.from_hex("#0088FF"),
        transform=Affine2D.rotation(0.2, origin=Point(55.0, 30.0)),
    )
    scene = Scene(240.0, 160.0, node)

    with pytest.raises(RuntimeError, match="native transform compositor"):
        list(scene.walk_composited())
