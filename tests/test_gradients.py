import math

import pytest

from swirui import Window
from swirui.rendering import (
    Color,
    GradientStop,
    LinearGradient,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def test_gradient_stop_validation_and_sampling() -> None:
    gradient = LinearGradient(
        start=Point(0.0, 0.5),
        end=Point(1.0, 0.5),
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
    assert gradient.color_at(-2.0) == gradient.stops[0].color
    assert gradient.color_at(2.0) == gradient.stops[-1].color

    with pytest.raises(ValueError, match="strictly increasing"):
        LinearGradient(
            Point(),
            Point(1.0, 0.0),
            (
                GradientStop(0.5, Color(1.0, 0.0, 0.0)),
                GradientStop(0.5, Color(0.0, 0.0, 1.0)),
            ),
        )
    with pytest.raises(ValueError, match="must differ"):
        LinearGradient.two_color(
            Color(1.0, 0.0, 0.0),
            Color(0.0, 0.0, 1.0),
            start=Point(0.5, 0.5),
            end=Point(0.5, 0.5),
        )


def test_horizontal_gradient_builds_retained_path_bands() -> None:
    gradient = LinearGradient.two_color(
        Color.from_hex("#0066FF"),
        Color.from_hex("#9B4DFF"),
    )
    bounds = Rect(40.0, 30.0, 320.0, 180.0)
    node = gradient.to_scene_node("hero", bounds, steps=16, opacity=0.8)

    assert node.kind is SceneNodeKind.GROUP
    assert node.bounds == bounds
    assert node.clip_to_bounds
    assert node.opacity == pytest.approx(0.8)
    assert len(node.children) == 16
    assert all(child.kind is SceneNodeKind.PATH for child in node.children)
    assert all(child.key == "hero" for child in node.children)
    assert all(child.path is not None for child in node.children)
    assert sum(child.path.triangle_count for child in node.children if child.path) == 32

    first = node.children[0].fill
    last = node.children[-1].fill
    assert first is not None and last is not None
    assert first.b < last.b or first.r < last.r


def test_diagonal_gradient_clips_every_band_to_bounds() -> None:
    gradient = LinearGradient(
        start=Point(-0.2, 0.1),
        end=Point(1.2, 0.9),
        stops=(
            GradientStop(0.0, Color.from_hex("#00D9FF")),
            GradientStop(0.4, Color.from_hex("#5F6CFF")),
            GradientStop(1.0, Color.from_hex("#E83EFF")),
        ),
    )
    bounds = Rect(10.0, 20.0, 500.0, 260.0)
    node = gradient.to_scene_node("diagonal", bounds, steps=48)

    assert len(node.children) >= 48
    for child in node.children:
        assert child.path is not None
        for point in child.path.points:
            assert -1.0e-7 <= point.x <= bounds.width + 1.0e-7
            assert -1.0e-7 <= point.y <= bounds.height + 1.0e-7
            assert math.isfinite(point.x)
            assert math.isfinite(point.y)


def test_gradient_scene_preserves_stable_hit_key() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 400.0, 240.0),
    )
    root.add(
        LinearGradient.two_color(
            Color.from_hex("#008CFF"),
            Color.from_hex("#8A2BE2"),
            start=Point(0.0, 0.0),
            end=Point(1.0, 1.0),
        ).to_scene_node("gradient-card", Rect(40.0, 30.0, 300.0, 160.0), steps=32)
    )
    scene = Scene(400.0, 240.0, root)

    target = scene.hit_test_xy(160.0, 100.0)
    assert target is not None
    assert target.key == "gradient-card"
    assert target.kind is SceneNodeKind.PATH


def test_gradient_flows_into_existing_wgpu_path_preparation() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 480.0, 320.0),
    )
    gradient = LinearGradient.two_color(
        Color.from_hex("#00C2FF"),
        Color.from_hex("#A855F7"),
        start=Point(0.0, 1.0),
        end=Point(1.0, 0.0),
    )
    root.add(gradient.to_scene_node("gpu-gradient", Rect(30.0, 40.0, 420.0, 220.0), steps=24))

    window = Window(width=480, height=320)
    window.set_scene(Scene(480.0, 320.0, root))
    vertices = WgpuRenderer()._path_vertices(window)

    assert len(vertices) >= 24 * 3
    assert len(vertices) % 3 == 0
    assert all(len(vertex) == 10 for vertex in vertices)
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
