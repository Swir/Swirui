import math

import pytest

from swirui import Window
from swirui.rendering import (
    Color,
    GradientStop,
    Point,
    RadialGradient,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def test_radial_gradient_validation_and_sampling() -> None:
    gradient = RadialGradient(
        center=Point(0.35, 0.6),
        radius=0.8,
        stops=(
            GradientStop(0.0, Color(1.0, 0.0, 0.0)),
            GradientStop(0.5, Color(0.0, 1.0, 0.0)),
            GradientStop(1.0, Color(0.0, 0.0, 1.0)),
        ),
    )

    quarter = gradient.color_at(0.25)
    assert quarter.r == pytest.approx(0.5)
    assert quarter.g == pytest.approx(0.5)
    assert quarter.b == pytest.approx(0.0)
    assert gradient.color_at(-1.0) == gradient.stops[0].color
    assert gradient.color_at(2.0) == gradient.stops[-1].color

    with pytest.raises(ValueError, match="radius"):
        RadialGradient.two_color(
            Color(1.0, 1.0, 1.0),
            Color(0.0, 0.0, 0.0),
            radius=0.0,
        )
    with pytest.raises(ValueError, match="finite"):
        RadialGradient(
            Point(math.inf, 0.5),
            1.0,
            (
                GradientStop(0.0, Color(1.0, 1.0, 1.0)),
                GradientStop(1.0, Color(0.0, 0.0, 0.0)),
            ),
        )


def test_radial_gradient_builds_edge_backing_and_nested_gpu_paths() -> None:
    bounds = Rect(30.0, 40.0, 360.0, 180.0)
    gradient = RadialGradient.two_color(
        Color.from_hex("#F8FAFF"),
        Color.from_hex("#3B2A80"),
        center=Point(0.4, 0.55),
        radius=0.85,
    )
    node = gradient.to_scene_node(
        "radial-card",
        bounds,
        steps=12,
        segments=24,
        opacity=0.75,
    )

    assert node.kind is SceneNodeKind.GROUP
    assert node.clip_to_bounds
    assert node.opacity == pytest.approx(0.75)
    assert len(node.children) == 13
    backing = node.children[0]
    assert backing.kind is SceneNodeKind.RECTANGLE
    assert backing.fill == gradient.color_at(1.0)
    disks = node.children[1:]
    assert all(child.kind is SceneNodeKind.PATH for child in disks)
    assert all(child.key == "radial-card" for child in disks)
    assert all(child.path is not None for child in disks)
    assert all(child.path and child.path.triangle_count == 22 for child in disks)

    first_disk = disks[0].path
    last_disk = disks[-1].path
    assert first_disk is not None and last_disk is not None
    assert first_disk.bounds.width > last_disk.bounds.width
    assert first_disk.bounds.height > last_disk.bounds.height


def test_radial_gradient_supports_off_center_ellipse_and_parent_clipping() -> None:
    bounds = Rect(20.0, 25.0, 500.0, 220.0)
    gradient = RadialGradient.two_color(
        Color.from_hex("#00F5FF"),
        Color.from_hex("#10122A"),
        center=Point(0.15, 0.8),
        radius=1.2,
    )
    node = gradient.to_scene_node("off-center", bounds, steps=8, segments=16)

    assert node.clip_to_bounds
    outer = node.children[1]
    assert outer.path is not None
    assert any(
        point.x < 0.0
        or point.y < 0.0
        or point.x > bounds.width
        or point.y > bounds.height
        for point in outer.path.points
    )


def test_radial_gradient_scene_preserves_one_stable_hit_key() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 280.0),
    )
    root.add(
        RadialGradient.two_color(
            Color.from_hex("#FFFFFF"),
            Color.from_hex("#221144"),
        ).to_scene_node("radial-panel", Rect(50.0, 40.0, 320.0, 190.0), steps=10, segments=20)
    )
    scene = Scene(420.0, 280.0, root)

    center_target = scene.hit_test_xy(210.0, 135.0)
    edge_target = scene.hit_test_xy(55.0, 45.0)
    assert center_target is not None and center_target.key == "radial-panel"
    assert edge_target is not None and edge_target.key == "radial-panel"


def test_radial_gradient_flows_into_existing_wgpu_shape_batch() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 480.0, 320.0),
    )
    root.add(
        RadialGradient.two_color(
            Color.from_hex("#F0FCFF"),
            Color.from_hex("#4338CA"),
            center=Point(0.45, 0.45),
        ).to_scene_node("gpu-radial", Rect(30.0, 40.0, 420.0, 220.0), steps=8, segments=16)
    )

    window = Window(width=480, height=320)
    window.set_scene(Scene(480.0, 320.0, root))
    vertices = WgpuRenderer()._path_vertices(window)

    assert len(vertices) == 8 * (16 - 2) * 3
    assert len(vertices) % 3 == 0
    assert all(len(vertex) == 10 for vertex in vertices)
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
