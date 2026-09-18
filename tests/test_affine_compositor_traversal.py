from __future__ import annotations

import math

import pytest

from swirui.rendering import Color, Point, Rect, Scene, SceneNode, SceneNodeKind
from swirui.rendering.affine import Affine2D


def test_inverse_transform_point_matches_materialized_inverse() -> None:
    transform = Affine2D.rotation(
        math.radians(37.0),
        origin=Point(80.0, 45.0),
    ).then(Affine2D.translation(19.0, -11.0))
    visual = Point(132.5, 74.25)

    direct = transform.inverse_transform_point(visual)
    materialized = transform.inverse().transform_point(visual)

    assert direct.x == pytest.approx(materialized.x)
    assert direct.y == pytest.approx(materialized.y)
    assert transform.transform_point(direct).x == pytest.approx(visual.x)
    assert transform.transform_point(direct).y == pytest.approx(visual.y)


def test_axis_alignment_classification_handles_composed_float_residue() -> None:
    assert Affine2D().is_axis_aligned is True
    assert Affine2D.translation(12.0, -4.0).is_axis_aligned is True
    assert Affine2D.uniform_scale(1.5, origin=Point(20.0, 10.0)).is_axis_aligned is True
    assert Affine2D.rotation(math.radians(18.0)).is_axis_aligned is False
    assert Affine2D.rotation(math.tau).is_axis_aligned is True


def test_affine_compositor_traversal_preserves_hierarchy_opacity_and_exact_clip() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 300.0),
        opacity=0.8,
        hit_testable=False,
    )
    parent = SceneNode(
        key="rotated-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(70.0, 60.0, 220.0, 140.0),
        opacity=0.5,
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(
            math.radians(24.0),
            origin=Point(180.0, 130.0),
        ),
    )
    child = SceneNode(
        key="translated-child",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(110.0, 90.0, 90.0, 48.0),
        fill=Color.from_hex("#0088FF"),
        opacity=0.5,
        transform=Affine2D.translation(16.0, -7.0),
    )
    parent.add(child)
    root.add(parent)
    scene = Scene(420.0, 300.0, root)

    records = {node.key: (opacity, clips, transform) for node, opacity, clips, transform in scene.walk_composited_affine()}

    parent_opacity, parent_clips, parent_world = records["rotated-clip"]
    child_opacity, child_clips, child_world = records["translated-child"]
    expected_child_world = child.transform.then(parent.transform)

    assert parent_opacity == pytest.approx(0.4)
    assert child_opacity == pytest.approx(0.2)
    assert parent_world == parent.transform
    assert child_world == expected_child_world
    assert parent_clips == ((parent.transform, parent.bounds),)
    assert child_clips == parent_clips

    authored = Point(137.0, 108.0)
    assert child_world.transform_point(authored) == expected_child_world.transform_point(authored)


def test_affine_compositor_traversal_accumulates_nested_clip_transforms() -> None:
    outer = SceneNode(
        key="outer",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(20.0, 20.0, 260.0, 200.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.translation(8.0, 4.0),
    )
    inner = SceneNode(
        key="inner",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(60.0, 50.0, 140.0, 100.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(
            math.radians(-15.0),
            origin=Point(130.0, 100.0),
        ),
    )
    leaf = SceneNode(
        key="leaf",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(80.0, 70.0, 70.0, 40.0),
        fill=Color.from_hex("#62E5FF"),
    )
    inner.add(leaf)
    outer.add(inner)
    scene = Scene(360.0, 260.0, outer)

    records = list(scene.walk_composited_affine())
    leaf_record = next(record for record in records if record[0] is leaf)
    clips = leaf_record[2]
    inner_world = inner.transform.then(outer.transform)

    assert clips == (
        (outer.transform, outer.bounds),
        (inner_world, inner.bounds),
    )
    assert leaf_record[3] == inner_world


def test_affine_compositor_traversal_prunes_fully_transparent_subtree() -> None:
    root = SceneNode(
        key="transparent-root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 320.0, 200.0),
        opacity=0.0,
        transform=Affine2D.rotation(0.25, origin=Point(160.0, 100.0)),
    )
    root.add(
        SceneNode(
            key="hidden-child",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(20.0, 20.0, 120.0, 60.0),
            fill=Color.from_hex("#0088FF"),
        )
    )

    assert list(Scene(320.0, 200.0, root).walk_composited_affine()) == []
