import math

import pytest

from swirui import VisualQuality, Window
from swirui.rendering import (
    Bloom,
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _bloom_layers(node: SceneNode) -> list[SceneNode]:
    return [layer for band in node.children for layer in band.children]


def test_bloom_validates_source_geometry_and_budget() -> None:
    with pytest.raises(ValueError, match="blur_radius"):
        Bloom(blur_radius=-0.01)
    with pytest.raises(ValueError, match="spread"):
        Bloom(spread=-0.01)
    with pytest.raises(ValueError, match="intensity"):
        Bloom(intensity=1.01)
    with pytest.raises(ValueError, match="steps"):
        Bloom(steps=0)
    with pytest.raises(ValueError, match="steps"):
        Bloom(steps=65)
    with pytest.raises(ValueError, match="finite"):
        Bloom(blur_radius=math.inf)

    bloom = Bloom()
    with pytest.raises(ValueError, match="keys"):
        bloom.to_scene_node("", Rect(0.0, 0.0, 10.0, 10.0))
    with pytest.raises(ValueError, match="positive dimensions"):
        bloom.to_scene_node("bad", Rect(0.0, 0.0, 0.0, 10.0))
    with pytest.raises(ValueError, match="opacity"):
        bloom.to_scene_node("bad", Rect(0.0, 0.0, 10.0, 10.0), opacity=1.1)


def test_bloom_compiles_two_band_normalized_light_spill() -> None:
    bloom = Bloom(
        color=Color(0.0, 0.65, 1.0, 0.6),
        blur_radius=30.0,
        spread=4.0,
        intensity=0.75,
        steps=9,
    )
    bounds = Rect(80.0, 60.0, 240.0, 120.0)
    radius = CornerRadius.uniform(18.0)
    node = bloom.to_scene_node(
        "emissive-card",
        bounds,
        corner_radius=radius,
        opacity=0.8,
        z_index=-2,
    )

    assert node.kind is SceneNodeKind.GROUP
    assert node.bounds == Rect(46.0, 26.0, 308.0, 188.0)
    assert node.opacity == pytest.approx(0.8)
    assert node.z_index == -2
    assert not node.hit_testable
    assert [band.key for band in node.children] == [
        "emissive-card:spill",
        "emissive-card:core",
    ]
    assert all(not band.hit_testable for band in node.children)

    layers = _bloom_layers(node)
    assert len(layers) == 9
    assert len({layer.key for layer in layers}) == 9
    assert all(not layer.hit_testable for layer in layers)
    assert all(layer.fill is not None for layer in layers)

    total_alpha = sum(layer.fill.a for layer in layers if layer.fill is not None)
    assert total_alpha == pytest.approx(bloom.color.a * bloom.intensity)
    assert node.children[0].bounds == node.bounds
    assert node.children[1].bounds.width < node.children[0].bounds.width
    assert node.children[1].bounds.height < node.children[0].bounds.height


def test_bloom_single_step_preserves_full_energy() -> None:
    bloom = Bloom(
        color=Color(0.2, 0.8, 1.0, 0.5),
        blur_radius=12.0,
        intensity=0.6,
        steps=1,
    )
    node = bloom.to_scene_node("one-step", Rect(20.0, 30.0, 80.0, 40.0))

    assert len(node.children) == 1
    assert node.children[0].key == "one-step:spill"
    layers = _bloom_layers(node)
    assert len(layers) == 1
    assert layers[0].fill is not None
    assert layers[0].fill.a == pytest.approx(0.3)


def test_bloom_quality_profiles_scale_work_without_changing_extent() -> None:
    bloom = Bloom(
        color=Color(0.1, 0.7, 1.0, 0.55),
        blur_radius=36.0,
        spread=3.0,
        intensity=0.8,
    )
    bounds = Rect(50.0, 70.0, 220.0, 110.0)
    radius = CornerRadius.uniform(20.0)

    performance = bloom.with_quality(VisualQuality.PERFORMANCE)
    cinematic = bloom.with_quality(VisualQuality.CINEMATIC)
    assert performance.steps == 4
    assert cinematic.steps == 32
    assert performance.color == cinematic.color == bloom.color
    assert performance.blur_radius == cinematic.blur_radius == bloom.blur_radius
    assert performance.spread == cinematic.spread == bloom.spread
    assert performance.intensity == cinematic.intensity == bloom.intensity

    low = performance.to_scene_node("low", bounds, corner_radius=radius)
    high = cinematic.to_scene_node("high", bounds, corner_radius=radius)
    assert low.bounds == high.bounds
    assert len(_bloom_layers(low)) == 4
    assert len(_bloom_layers(high)) == 32

    low_alpha = sum(layer.fill.a for layer in _bloom_layers(low) if layer.fill is not None)
    high_alpha = sum(layer.fill.a for layer in _bloom_layers(high) if layer.fill is not None)
    assert low_alpha == pytest.approx(high_alpha)


def test_bloom_does_not_steal_hits_and_flows_into_gpu_rectangle_batch() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 280.0),
    )
    source_bounds = Rect(100.0, 80.0, 220.0, 120.0)
    radius = CornerRadius.uniform(24.0)
    root.add(
        Bloom(
            color=Color(0.0, 0.58, 1.0, 0.5),
            blur_radius=28.0,
            spread=2.0,
            intensity=0.8,
            steps=8,
        ).to_scene_node(
            "bloom",
            source_bounds,
            corner_radius=radius,
            z_index=5,
        ),
        SceneNode(
            key="background",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(0.0, 0.0, 420.0, 280.0),
            fill=Color.from_hex("#050815"),
            z_index=0,
        ),
        SceneNode(
            key="source",
            kind=SceneNodeKind.RECTANGLE,
            bounds=source_bounds,
            fill=Color.from_hex("#0E1B39"),
            corner_radius=radius,
            z_index=6,
        ),
    )
    scene = Scene(420.0, 280.0, root)

    assert scene.hit_test_xy(120.0, 100.0).key == "source"
    assert scene.hit_test_xy(90.0, 70.0).key == "background"

    window = Window(width=420, height=280)
    window.set_scene(scene)
    rectangles = WgpuRenderer()._rectangle_instances(window)

    assert len(rectangles) == 10
    assert all(len(instance) == 16 for instance in rectangles)
    assert all(math.isfinite(value) for instance in rectangles for value in instance)
