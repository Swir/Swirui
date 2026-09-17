import pytest

from swirui.core import VisualQuality
from swirui.rendering import Color, Noise, Point, Rect, Scene, SceneNode, SceneNodeKind


def test_noise_builds_deterministic_clipped_noninteractive_grain() -> None:
    effect = Noise(
        samples=12,
        size=1.5,
        color=Color(0.9, 0.95, 1.0, 0.08),
        seed=12345,
    )
    bounds = Rect(30.0, 40.0, 240.0, 150.0)

    first = effect.to_scene_node("noise", bounds, z_index=7)
    second = effect.to_scene_node("noise", bounds, z_index=7)

    assert first.kind is SceneNodeKind.GROUP
    assert first.bounds == bounds
    assert first.z_index == 7
    assert first.clip_to_bounds is True
    assert first.hit_testable is False
    assert len(first.children) == 12
    assert [child.bounds for child in first.children] == [
        child.bounds for child in second.children
    ]
    assert all(child.kind is SceneNodeKind.RECTANGLE for child in first.children)
    assert all(child.fill == effect.color for child in first.children)
    assert all(child.hit_testable is False for child in first.children)
    assert all(bounds.contains(Point(child.bounds.x, child.bounds.y)) for child in first.children)


def test_noise_seed_changes_retained_distribution() -> None:
    bounds = Rect(0.0, 0.0, 320.0, 180.0)
    first = Noise(samples=8, seed=1).to_scene_node("a", bounds)
    second = Noise(samples=8, seed=2).to_scene_node("b", bounds)

    assert [child.bounds for child in first.children] != [child.bounds for child in second.children]


def test_noise_quality_profiles_scale_only_sample_budget() -> None:
    effect = Noise(samples=3, size=2.0, seed=77, color=Color(0.2, 0.3, 0.4, 0.1))
    qualities = (
        VisualQuality.PERFORMANCE,
        VisualQuality.BALANCED,
        VisualQuality.QUALITY,
        VisualQuality.ULTRA,
        VisualQuality.CINEMATIC,
    )
    variants = [effect.with_quality(quality) for quality in qualities]

    assert [variant.samples for variant in variants] == [16, 32, 64, 96, 128]
    assert all(variant.size == effect.size for variant in variants)
    assert all(variant.seed == effect.seed for variant in variants)
    assert all(variant.color == effect.color for variant in variants)
    assert effect.with_quality(VisualQuality.AUTO).samples == 48


def test_noise_zero_samples_or_transparent_color_produces_empty_group() -> None:
    bounds = Rect(0.0, 0.0, 180.0, 120.0)

    assert Noise(samples=0).to_scene_node("zero", bounds).children == []
    assert Noise(color=Color(1.0, 1.0, 1.0, 0.0)).to_scene_node(
        "transparent", bounds
    ).children == []


def test_noise_overlay_does_not_steal_pointer_hits() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 360.0, 240.0))
    button = SceneNode(
        "button",
        SceneNodeKind.RECTANGLE,
        Rect(80.0, 70.0, 180.0, 80.0),
        fill=Color.from_hex("#168DFF"),
        z_index=1,
    )
    noise = Noise(samples=32).to_scene_node(
        "noise",
        Rect(50.0, 50.0, 240.0, 140.0),
        z_index=2,
    )
    root.add(button, noise)
    scene = Scene(360.0, 240.0, root)

    assert scene.hit_test(Point(120.0, 100.0)) is button


def test_noise_validates_cost_and_size() -> None:
    with pytest.raises(ValueError, match="samples"):
        Noise(samples=-1)
    with pytest.raises(ValueError, match="samples"):
        Noise(samples=513)
    with pytest.raises(ValueError, match="size"):
        Noise(size=0.1)
    with pytest.raises(ValueError, match="size"):
        Noise(size=float("nan"))
