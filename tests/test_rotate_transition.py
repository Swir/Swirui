from __future__ import annotations

import math

import pytest

from swirui import RotateTransition, Widget, linear
from swirui.rendering import Affine2D, Color, Point, Rect, SceneNode, SceneNodeKind
from swirui.widgets.runtime import compile_component_scene


class _SolidTile(Widget):
    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            fill=Color(0.1, 0.55, 0.95, 1.0),
            clip_to_bounds=self.clip_to_bounds,
        )


def _scene_for(widget: Widget):
    scene = compile_component_scene(widget, width=420.0, height=300.0)
    assert scene is not None
    return scene


def test_visual_rotation_compiles_one_center_origin_affine_transform() -> None:
    tile = _SolidTile(bounds=Rect(20.0, 30.0, 120.0, 40.0), key="rotate-tile")
    authored_bounds = tile.bounds
    authored_preferred = tile.preferred_size
    tile.visual_rotation = math.pi * 0.5

    scene = _scene_for(tile)
    expected = Affine2D.rotation(math.pi * 0.5, origin=Point(80.0, 50.0))

    assert scene.has_affine_transforms is True
    assert scene.root.transform == expected
    assert tile.bounds == authored_bounds
    assert tile.preferred_size == authored_preferred

    authored_inside = Point(24.0, 34.0)
    visual_inside = expected.transform_point(authored_inside)
    assert scene.hit_test(visual_inside) is scene.root


def test_visual_rotation_is_applied_after_scale_and_translation() -> None:
    tile = _SolidTile(bounds=Rect(20.0, 30.0, 120.0, 40.0), key="composed-tile")
    tile.visual_scale = 0.5
    tile.set_visual_offset(12.0, -4.0)
    tile.set_visual_rotation(math.pi / 3.0)

    scene = _scene_for(tile)

    assert scene.root.bounds == Rect(62.0, 36.0, 60.0, 20.0)
    expected = Affine2D.rotation(math.pi / 3.0, origin=Point(92.0, 46.0))
    assert scene.root.transform == expected
    assert tile.bounds == Rect(20.0, 30.0, 120.0, 40.0)


def test_rotate_transition_samples_restores_and_keeps_layout_stable() -> None:
    tile = _SolidTile(bounds=Rect(40.0, 50.0, 100.0, 48.0), key="transition-tile")
    tile.visual_rotation = 0.25
    authored_bounds = tile.bounds
    authored_preferred = tile.preferred_size

    transition = RotateTransition(
        tile,
        math.pi,
        duration=1.0,
        easing=linear,
    ).start()
    transition.advance(0.5)

    assert tile.visual_rotation == pytest.approx(0.25 + (math.pi - 0.25) * 0.5)
    assert tile.bounds == authored_bounds
    assert tile.preferred_size == authored_preferred

    sampled = tile.visual_rotation
    assert transition.cancel() is True
    assert tile.visual_rotation == pytest.approx(sampled)
    transition.restore()
    assert tile.visual_rotation == pytest.approx(0.25)


def test_rotate_transition_is_frame_partition_independent() -> None:
    first = _SolidTile(bounds=Rect(0.0, 0.0, 100.0, 40.0), key="first")
    second = _SolidTile(bounds=Rect(0.0, 0.0, 100.0, 40.0), key="second")
    first_transition = RotateTransition(first, 1.75, duration=1.0).start()
    second_transition = RotateTransition(second, 1.75, duration=1.0).start()

    first_transition.advance(0.4)
    for _ in range(8):
        second_transition.advance(0.05)

    assert first.visual_rotation == pytest.approx(second.visual_rotation)


def test_visual_rotation_and_transition_validation_are_strict() -> None:
    tile = _SolidTile(bounds=Rect(0.0, 0.0, 100.0, 40.0), key="validate")

    with pytest.raises(ValueError, match="visual_rotation"):
        tile.visual_rotation = math.nan
    with pytest.raises(ValueError, match="visual_rotation"):
        tile.visual_rotation = math.inf
    with pytest.raises(ValueError, match="to_radians"):
        RotateTransition(tile, math.nan)
    with pytest.raises(ValueError, match="duration"):
        RotateTransition(tile, 1.0, duration=-0.01)
