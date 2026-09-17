import pytest

from swirui.core import VisualQuality
from swirui.rendering import (
    Acrylic,
    Color,
    CornerRadius,
    FrostedGlass,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)


def test_frosted_glass_builds_backdrop_border_and_tint_layers() -> None:
    material = FrostedGlass(
        blur_radius=24.0,
        tint=Color(0.08, 0.12, 0.20, 0.40),
        border_color=Color(0.8, 0.9, 1.0, 0.30),
        border_width=2.0,
        corner_radius=CornerRadius.uniform(20.0),
    )
    node = material.to_scene_node("glass", Rect(20.0, 30.0, 300.0, 180.0), z_index=4)

    assert node.kind is SceneNodeKind.BACKDROP_BLUR
    assert node.blur_radius == 24.0
    assert node.z_index == 4
    assert node.clip_to_bounds is True
    assert node.hit_testable is False
    assert [child.key for child in node.children] == ["glass:border", "glass:tint"]

    border, tint = node.children
    assert border.bounds == Rect(20.0, 30.0, 300.0, 180.0)
    assert border.corner_radius == CornerRadius.uniform(20.0)
    assert border.fill == material.border_color
    assert border.hit_testable is False

    assert tint.bounds == Rect(22.0, 32.0, 296.0, 176.0)
    assert tint.corner_radius == CornerRadius.uniform(18.0)
    assert tint.fill == material.tint
    assert tint.hit_testable is False


def test_frosted_glass_decorations_do_not_steal_hits_from_controls() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 480.0, 320.0))
    glass = FrostedGlass().to_scene_node("glass", Rect(80.0, 60.0, 300.0, 180.0))
    button = SceneNode(
        "button",
        SceneNodeKind.RECTANGLE,
        Rect(150.0, 135.0, 140.0, 52.0),
        fill=Color.from_hex("#168DFF"),
        corner_radius=CornerRadius.uniform(12.0),
        z_index=10,
    )
    glass.add(button)
    root.add(glass)
    scene = Scene(480.0, 320.0, root)

    assert scene.hit_test(Point(180.0, 155.0)) is button


def test_frosted_glass_validates_border_geometry() -> None:
    with pytest.raises(ValueError, match="border_width"):
        FrostedGlass(border_width=-0.1)
    with pytest.raises(ValueError, match="border_width"):
        FrostedGlass(border_width=float("inf"))
    with pytest.raises(ValueError, match="too large"):
        FrostedGlass(border_width=8.0).to_scene_node(
            "tiny",
            Rect(0.0, 0.0, 14.0, 30.0),
        )


def test_acrylic_builds_deterministic_luminosity_and_micro_grain() -> None:
    material = Acrylic(
        blur_radius=28.0,
        grain_samples=8,
        grain_size=1.5,
        grain_seed=12345,
        corner_radius=CornerRadius.uniform(18.0),
    )
    first = material.to_scene_node("acrylic", Rect(10.0, 20.0, 320.0, 210.0))
    second = material.to_scene_node("acrylic", Rect(10.0, 20.0, 320.0, 210.0))

    assert first.kind is SceneNodeKind.BACKDROP_BLUR
    assert first.blur_radius == 28.0
    assert [child.key for child in first.children] == [
        "acrylic:border",
        "acrylic:tint",
        "acrylic:luminosity",
        "acrylic:grain",
    ]
    grain = first.children[-1]
    other_grain = second.children[-1]
    assert grain.kind is SceneNodeKind.GROUP
    assert grain.clip_to_bounds is True
    assert grain.hit_testable is False
    assert len(grain.children) == 8
    assert [dot.bounds for dot in grain.children] == [dot.bounds for dot in other_grain.children]
    assert all(dot.hit_testable is False for dot in grain.children)
    assert all(grain.bounds.contains(Point(dot.bounds.x, dot.bounds.y)) for dot in grain.children)


def test_acrylic_quality_profiles_scale_only_grain_density() -> None:
    material = Acrylic(blur_radius=31.0, grain_samples=3, grain_seed=77)
    qualities = (
        VisualQuality.PERFORMANCE,
        VisualQuality.BALANCED,
        VisualQuality.QUALITY,
        VisualQuality.ULTRA,
        VisualQuality.CINEMATIC,
    )
    variants = [material.with_quality(quality) for quality in qualities]

    assert [variant.grain_samples for variant in variants] == [12, 24, 48, 72, 96]
    assert all(variant.blur_radius == material.blur_radius for variant in variants)
    assert all(variant.tint == material.tint for variant in variants)
    assert all(variant.corner_radius == material.corner_radius for variant in variants)
    assert material.with_quality(VisualQuality.AUTO).grain_samples == 40


def test_acrylic_can_disable_grain_without_disabling_backdrop() -> None:
    node = Acrylic(grain_samples=0).to_scene_node("plain", Rect(0.0, 0.0, 240.0, 140.0))

    assert node.kind is SceneNodeKind.BACKDROP_BLUR
    assert [child.key for child in node.children] == [
        "plain:border",
        "plain:tint",
        "plain:luminosity",
    ]


def test_acrylic_validates_grain_budget_and_size() -> None:
    with pytest.raises(ValueError, match="grain_samples"):
        Acrylic(grain_samples=193)
    with pytest.raises(ValueError, match="grain_size"):
        Acrylic(grain_size=0.1)
    with pytest.raises(ValueError, match="grain_size"):
        Acrylic(grain_size=float("nan"))
