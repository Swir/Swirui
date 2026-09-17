import math

import pytest

from swirui import VisualQuality, Window
from swirui.rendering import (
    Color,
    Point,
    Rect,
    Reflection,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def test_reflection_resolves_normalized_specular_band() -> None:
    reflection = Reflection(
        color=Color(0.8, 0.92, 1.0, 0.35),
        angle_degrees=0.0,
        position=0.4,
        width=0.2,
        steps=16,
    )

    gradient = reflection.resolved_gradient()

    assert gradient.start == Point(0.0, 0.5)
    assert gradient.end == Point(1.0, 0.5)
    assert tuple(stop.offset for stop in gradient.stops) == pytest.approx(
        (0.0, 0.3, 0.4, 0.5, 1.0)
    )
    assert gradient.stops[2].color == reflection.color
    assert gradient.stops[0].color.a == 0.0
    assert gradient.stops[-1].color.a == 0.0


def test_reflection_angle_keeps_gradient_coverage_finite() -> None:
    gradient = Reflection(angle_degrees=37.0).resolved_gradient()

    assert gradient.start != gradient.end
    assert all(
        math.isfinite(value)
        for point in (gradient.start, gradient.end)
        for value in (point.x, point.y)
    )


def test_reflection_quality_scales_only_tessellation_budget() -> None:
    reflection = Reflection(
        color=Color(0.72, 0.9, 1.0, 0.24),
        angle_degrees=-18.0,
        position=0.58,
        width=0.22,
    )

    performance = reflection.with_quality(VisualQuality.PERFORMANCE)
    cinematic = reflection.with_quality(VisualQuality.CINEMATIC)

    assert performance.steps == 12
    assert cinematic.steps == 96
    assert performance.color == cinematic.color == reflection.color
    assert performance.angle_degrees == cinematic.angle_degrees == reflection.angle_degrees
    assert performance.position == cinematic.position == reflection.position
    assert performance.width == cinematic.width == reflection.width


def test_reflection_validates_geometry_and_budget() -> None:
    with pytest.raises(ValueError, match="position"):
        Reflection(position=0.0)
    with pytest.raises(ValueError, match="position"):
        Reflection(position=1.0)
    with pytest.raises(ValueError, match="width"):
        Reflection(width=0.0)
    with pytest.raises(ValueError, match="width"):
        Reflection(width=2.1)
    with pytest.raises(ValueError, match="steps"):
        Reflection(steps=1)
    with pytest.raises(ValueError, match="steps"):
        Reflection(steps=257)
    with pytest.raises(ValueError, match="finite"):
        Reflection(angle_degrees=math.inf)


def test_reflection_builds_clipped_noninteractive_retained_paths() -> None:
    bounds = Rect(80.0, 60.0, 280.0, 160.0)
    node = Reflection(position=0.45, width=0.2, steps=12).to_scene_node(
        "card-reflection",
        bounds,
        opacity=0.7,
        z_index=3,
    )

    assert node.kind is SceneNodeKind.GROUP
    assert node.bounds == bounds
    assert node.opacity == pytest.approx(0.7)
    assert node.z_index == 3
    assert node.clip_to_bounds
    assert not node.hit_testable
    assert node.children
    assert all(child.kind is SceneNodeKind.PATH for child in node.children)
    assert all(not child.hit_testable for child in node.children)
    assert all(child.bounds == bounds for child in node.children)


def test_reflection_does_not_steal_scene_hits() -> None:
    bounds = Rect(90.0, 70.0, 220.0, 120.0)
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 400.0, 260.0))
    root.add(
        SceneNode(
            "background",
            SceneNodeKind.RECTANGLE,
            Rect(0.0, 0.0, 400.0, 260.0),
            fill=Color.from_hex("#06101F"),
        ),
        SceneNode(
            "card",
            SceneNodeKind.RECTANGLE,
            bounds,
            fill=Color.from_hex("#173B6C"),
            z_index=1,
        ),
        Reflection(steps=10).to_scene_node("reflection", bounds, z_index=2),
    )
    scene = Scene(400.0, 260.0, root)

    assert scene.hit_test_xy(150.0, 110.0).key == "card"
    assert scene.hit_test_xy(20.0, 20.0).key == "background"


def test_reflection_flows_into_existing_wgpu_path_batch() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 520.0, 340.0))
    bounds = Rect(110.0, 80.0, 300.0, 180.0)
    root.add(
        SceneNode(
            "card",
            SceneNodeKind.RECTANGLE,
            bounds,
            fill=Color.from_hex("#102B4F"),
        ),
        Reflection(
            angle_degrees=28.0,
            position=0.42,
            width=0.16,
            steps=8,
        ).to_scene_node("reflection", bounds, z_index=1),
    )
    window = Window(width=520, height=340)
    window.set_scene(Scene(520.0, 340.0, root))

    vertices = WgpuRenderer()._path_vertices(window)

    assert vertices
    assert len(vertices) % 3 == 0
    assert all(len(vertex) == 10 for vertex in vertices)
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
