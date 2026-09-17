import math

import pytest

from swirui import Window
from swirui.rendering import (
    Color,
    CornerRadius,
    DropShadow,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def test_drop_shadow_validates_geometry_and_quality() -> None:
    with pytest.raises(ValueError, match="blur_radius"):
        DropShadow(blur_radius=-1.0)
    with pytest.raises(ValueError, match="spread"):
        DropShadow(spread=-1.0)
    with pytest.raises(ValueError, match="steps"):
        DropShadow(steps=0)
    with pytest.raises(ValueError, match="steps"):
        DropShadow(steps=65)
    with pytest.raises(ValueError, match="finite"):
        DropShadow(offset=Point(math.inf, 0.0))


def test_drop_shadow_builds_normalized_retained_layers() -> None:
    shadow = DropShadow(
        color=Color(0.1, 0.2, 0.4, 0.48),
        offset=Point(6.0, 10.0),
        blur_radius=24.0,
        spread=4.0,
        steps=6,
    )
    bounds = Rect(40.0, 50.0, 220.0, 120.0)
    radius = CornerRadius(8.0, 12.0, 16.0, 20.0)
    node = shadow.to_scene_node(
        "card-shadow",
        bounds,
        corner_radius=radius,
        opacity=0.75,
        z_index=-1,
    )

    assert node.kind is SceneNodeKind.GROUP
    assert node.bounds == Rect(18.0, 32.0, 276.0, 176.0)
    assert node.opacity == pytest.approx(0.75)
    assert node.z_index == -1
    assert not node.hit_testable
    assert len(node.children) == 6
    assert all(child.kind is SceneNodeKind.RECTANGLE for child in node.children)
    assert all(not child.hit_testable for child in node.children)
    assert all(child.fill is not None for child in node.children)

    alpha_sum = sum(child.fill.a for child in node.children if child.fill is not None)
    assert alpha_sum == pytest.approx(shadow.color.a)

    outer = node.children[0]
    inner = node.children[-1]
    assert outer.bounds == node.bounds
    assert inner.bounds.width < outer.bounds.width
    assert inner.bounds.height < outer.bounds.height
    assert outer.corner_radius == CornerRadius(36.0, 40.0, 44.0, 48.0)
    assert inner.corner_radius.top_left > radius.top_left


def test_drop_shadow_zero_blur_uses_one_spread_layer() -> None:
    shadow = DropShadow(
        color=Color(0.0, 0.0, 0.0, 0.5),
        offset=Point(-3.0, 5.0),
        blur_radius=0.0,
        spread=3.0,
        steps=8,
    )
    node = shadow.to_scene_node(
        "hard-shadow",
        Rect(20.0, 30.0, 100.0, 60.0),
        corner_radius=CornerRadius.uniform(7.0),
    )

    assert len(node.children) == 1
    layer = node.children[0]
    assert layer.bounds == Rect(14.0, 32.0, 106.0, 66.0)
    assert layer.fill == Color(0.0, 0.0, 0.0, 0.5)
    assert layer.corner_radius == CornerRadius.uniform(10.0)


def test_decorative_shadow_does_not_steal_scene_hits() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 360.0, 240.0),
    )
    shadow = DropShadow(offset=Point(0.0, 16.0), blur_radius=30.0, steps=8)
    root.add(
        shadow.to_scene_node(
            "shadow",
            Rect(90.0, 60.0, 180.0, 100.0),
            corner_radius=CornerRadius.uniform(18.0),
            z_index=5,
        ),
        SceneNode(
            key="background-target",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(0.0, 0.0, 360.0, 240.0),
            fill=Color(0.1, 0.1, 0.1),
            z_index=0,
        ),
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(90.0, 60.0, 180.0, 100.0),
            fill=Color(0.9, 0.9, 0.9),
            z_index=6,
        ),
    )
    scene = Scene(360.0, 240.0, root)

    assert scene.hit_test_xy(120.0, 100.0).key == "card"
    assert scene.hit_test_xy(100.0, 185.0).key == "background-target"


def test_drop_shadow_flows_into_existing_wgpu_rectangle_batch() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 280.0),
    )
    card_bounds = Rect(90.0, 70.0, 240.0, 130.0)
    root.add(
        DropShadow(blur_radius=20.0, spread=2.0, steps=5).to_scene_node(
            "shadow",
            card_bounds,
            corner_radius=CornerRadius.uniform(20.0),
        ),
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=card_bounds,
            fill=Color.from_hex("#172554"),
            corner_radius=CornerRadius.uniform(20.0),
        ),
    )

    window = Window(width=420, height=280)
    window.set_scene(Scene(420.0, 280.0, root))
    rectangles = WgpuRenderer()._rectangle_instances(window)

    assert len(rectangles) == 6
    assert all(len(instance) == 16 for instance in rectangles)
    assert all(math.isfinite(value) for instance in rectangles for value in instance)
