import math

import pytest

from swirui import VisualQuality, Window
from swirui.rendering import (
    AdaptiveLighting,
    Color,
    CornerRadius,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def test_adaptive_lighting_resolves_opposed_shadow_and_highlight() -> None:
    lighting = AdaptiveLighting(
        elevation=20.0,
        light_direction_degrees=270.0,
        light_altitude_degrees=45.0,
        shadow_softness=1.5,
        highlight_softness=0.6,
        highlight_offset_ratio=0.25,
        steps=8,
    )

    shadow, highlight = lighting.resolved_lobes()

    assert shadow.offset.x == pytest.approx(0.0, abs=1e-9)
    assert shadow.offset.y == pytest.approx(20.0)
    assert highlight.offset.x == pytest.approx(0.0, abs=1e-9)
    assert highlight.offset.y == pytest.approx(-5.0)
    assert shadow.blur_radius == pytest.approx(30.0)
    assert highlight.blur_radius == pytest.approx(12.0)
    assert shadow.steps == highlight.steps == 8


def test_adaptive_lighting_overhead_light_centers_both_lobes() -> None:
    shadow, highlight = AdaptiveLighting(
        elevation=30.0,
        light_direction_degrees=35.0,
        light_altitude_degrees=90.0,
    ).resolved_lobes()

    assert shadow.offset == Point()
    assert highlight.offset == Point()


def test_adaptive_lighting_quality_scales_only_retained_layer_budget() -> None:
    lighting = AdaptiveLighting(
        elevation=18.0,
        light_direction_degrees=225.0,
        light_altitude_degrees=52.0,
        shadow_softness=1.4,
        highlight_softness=0.55,
        highlight_offset_ratio=0.28,
        spread=1.5,
    )

    performance = lighting.with_quality(VisualQuality.PERFORMANCE)
    cinematic = lighting.with_quality(VisualQuality.CINEMATIC)

    assert performance.steps == 6
    assert cinematic.steps == 40
    assert performance.elevation == cinematic.elevation == lighting.elevation
    assert performance.light_direction_degrees == lighting.light_direction_degrees
    assert cinematic.light_altitude_degrees == lighting.light_altitude_degrees
    assert performance.shadow_color == cinematic.shadow_color == lighting.shadow_color
    assert performance.highlight_color == cinematic.highlight_color == lighting.highlight_color
    assert performance.highlight_offset_ratio == lighting.highlight_offset_ratio


def test_adaptive_lighting_validates_light_model() -> None:
    with pytest.raises(ValueError, match="elevation"):
        AdaptiveLighting(elevation=-1.0)
    with pytest.raises(ValueError, match="light_altitude_degrees"):
        AdaptiveLighting(light_altitude_degrees=0.0)
    with pytest.raises(ValueError, match="light_altitude_degrees"):
        AdaptiveLighting(light_altitude_degrees=91.0)
    with pytest.raises(ValueError, match="shadow_softness"):
        AdaptiveLighting(shadow_softness=-0.1)
    with pytest.raises(ValueError, match="highlight_softness"):
        AdaptiveLighting(highlight_softness=-0.1)
    with pytest.raises(ValueError, match="highlight_offset_ratio"):
        AdaptiveLighting(highlight_offset_ratio=-0.1)
    with pytest.raises(ValueError, match="highlight_offset_ratio"):
        AdaptiveLighting(highlight_offset_ratio=1.1)
    with pytest.raises(ValueError, match="spread"):
        AdaptiveLighting(spread=-1.0)
    with pytest.raises(ValueError, match="steps"):
        AdaptiveLighting(steps=0)
    with pytest.raises(ValueError, match="steps"):
        AdaptiveLighting(steps=65)
    with pytest.raises(ValueError, match="finite"):
        AdaptiveLighting(light_direction_degrees=math.inf)


def test_adaptive_lighting_builds_two_normalized_noninteractive_lobes() -> None:
    bounds = Rect(80.0, 70.0, 220.0, 120.0)
    radius = CornerRadius.uniform(18.0)
    lighting = AdaptiveLighting(
        elevation=16.0,
        light_direction_degrees=270.0,
        light_altitude_degrees=45.0,
        shadow_color=Color(0.0, 0.0, 0.0, 0.32),
        highlight_color=Color(0.7, 0.9, 1.0, 0.18),
        shadow_softness=1.5,
        highlight_softness=0.5,
        highlight_offset_ratio=0.25,
        steps=4,
    )

    node = lighting.to_scene_node(
        "card-lighting",
        bounds,
        corner_radius=radius,
        opacity=0.75,
        z_index=-2,
    )

    assert node.kind is SceneNodeKind.GROUP
    assert node.opacity == pytest.approx(0.75)
    assert node.z_index == -2
    assert not node.hit_testable
    assert [child.key for child in node.children] == [
        "card-lighting:shadow",
        "card-lighting:highlight",
    ]
    assert all(not child.hit_testable for child in node.children)
    assert all(len(child.children) == 4 for child in node.children)
    assert node.bounds.x == pytest.approx(56.0)
    assert node.bounds.y == pytest.approx(58.0)
    assert node.bounds.width == pytest.approx(268.0)
    assert node.bounds.height == pytest.approx(172.0)

    shadow_alpha = sum(
        layer.fill.a
        for layer in node.children[0].children
        if layer.fill is not None
    )
    highlight_alpha = sum(
        layer.fill.a
        for layer in node.children[1].children
        if layer.fill is not None
    )
    assert shadow_alpha == pytest.approx(lighting.shadow_color.a)
    assert highlight_alpha == pytest.approx(lighting.highlight_color.a)


def test_adaptive_lighting_handles_zero_elevation_and_transparent_lobes() -> None:
    bounds = Rect(10.0, 20.0, 180.0, 100.0)

    flat = AdaptiveLighting(elevation=0.0).to_scene_node("flat", bounds)
    assert flat.bounds == bounds
    assert flat.children == []

    highlight_only = AdaptiveLighting(
        shadow_color=Color(0.0, 0.0, 0.0, 0.0),
        highlight_color=Color(1.0, 1.0, 1.0, 0.2),
        steps=3,
    ).to_scene_node("highlight-only", bounds)
    assert len(highlight_only.children) == 1
    assert highlight_only.children[0].key == "highlight-only:highlight"


def test_adaptive_lighting_moves_when_direction_changes() -> None:
    bounds = Rect(80.0, 70.0, 180.0, 100.0)
    from_above = AdaptiveLighting(
        elevation=18.0,
        light_direction_degrees=270.0,
        light_altitude_degrees=45.0,
        steps=4,
    ).to_scene_node("lighting", bounds)
    from_left = AdaptiveLighting(
        elevation=18.0,
        light_direction_degrees=180.0,
        light_altitude_degrees=45.0,
        steps=4,
    ).to_scene_node("lighting", bounds)

    assert from_above.bounds != from_left.bounds
    assert from_above.children[0].bounds != from_left.children[0].bounds
    assert from_above.children[1].bounds != from_left.children[1].bounds


def test_adaptive_lighting_does_not_steal_scene_hits() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 360.0, 240.0))
    bounds = Rect(90.0, 60.0, 180.0, 100.0)
    root.add(
        SceneNode(
            "background",
            SceneNodeKind.RECTANGLE,
            Rect(0.0, 0.0, 360.0, 240.0),
            fill=Color(0.05, 0.05, 0.05),
            z_index=0,
        ),
        SceneNode(
            "card",
            SceneNodeKind.RECTANGLE,
            bounds,
            fill=Color(0.2, 0.3, 0.5),
            z_index=1,
        ),
        AdaptiveLighting(elevation=18.0, steps=5).to_scene_node(
            "lighting",
            bounds,
            corner_radius=CornerRadius.uniform(18.0),
            z_index=2,
        ),
    )
    scene = Scene(360.0, 240.0, root)

    assert scene.hit_test_xy(120.0, 100.0).key == "card"
    assert scene.hit_test_xy(100.0, 200.0).key == "background"


def test_adaptive_lighting_flows_into_existing_wgpu_rectangle_batch() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 420.0, 280.0))
    bounds = Rect(90.0, 70.0, 240.0, 130.0)
    root.add(
        AdaptiveLighting(elevation=14.0, steps=4).to_scene_node(
            "lighting",
            bounds,
            corner_radius=CornerRadius.uniform(20.0),
        ),
        SceneNode(
            "card",
            SceneNodeKind.RECTANGLE,
            bounds,
            fill=Color.from_hex("#172554"),
        ),
    )

    window = Window(width=420, height=280)
    window.set_scene(Scene(420.0, 280.0, root))
    rectangles = WgpuRenderer()._rectangle_instances(window)

    assert len(rectangles) == 9
    assert all(len(instance) == 16 for instance in rectangles)
    assert all(math.isfinite(value) for instance in rectangles for value in instance)
