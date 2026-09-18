from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationParallel,
    Button,
    Card,
    FadeTransition,
    Label,
    ScaleTransition,
    SlideTransition,
    linear,
)
from swirui.rendering import Point, Rect
from swirui.widgets.runtime import compile_component_scene


def _button() -> Button:
    button = Button("Animate", bounds=Rect(20.0, 30.0, 180.0, 52.0), opacity=0.8)
    button.visual_offset = Point(3.0, 5.0)
    return button


def test_fade_transition_preserves_authored_opacity_for_default_target() -> None:
    button = _button()
    transition = FadeTransition(
        button,
        from_opacity=0.0,
        duration=1.0,
        easing=linear,
    ).start()

    assert button.opacity == pytest.approx(0.0)
    transition.advance(0.5)
    assert button.opacity == pytest.approx(0.4)
    assert transition.advance(0.75) == pytest.approx(0.25)
    assert button.opacity == pytest.approx(0.8)

    transition.restore()
    assert button.opacity == pytest.approx(0.8)


def test_slide_transition_uses_relative_visual_offsets_without_layout_changes() -> None:
    button = _button()
    authored_bounds = button.bounds
    transition = SlideTransition(
        button,
        from_offset=Point(40.0, -10.0),
        to_offset=Point(-20.0, 30.0),
        duration=1.0,
        easing=linear,
    ).start()

    assert button.visual_offset == Point(43.0, -5.0)
    transition.advance(0.5)
    assert button.visual_offset == Point(13.0, 15.0)
    assert button.bounds == authored_bounds

    transition.advance(0.5)
    assert button.visual_offset == Point(-17.0, 35.0)
    assert button.bounds == authored_bounds

    transition.restore()
    assert button.visual_offset == Point(3.0, 5.0)


def test_scale_transition_transforms_compiled_subtree_without_layout_changes() -> None:
    card = Card(key="scale-card", bounds=Rect(100.0, 100.0, 200.0, 100.0))
    label = Label("Scale", key="scale-label", bounds=Rect(120.0, 120.0, 100.0, 30.0))
    card.add(label)
    authored_card_bounds = card.bounds
    authored_label_bounds = label.bounds
    authored_font_size = label.font_size
    transition = ScaleTransition(
        card,
        from_scale=0.5,
        duration=1.0,
        easing=linear,
    ).start()

    scene = compile_component_scene(card, width=500.0, height=400.0)
    assert scene is not None
    card_node = next(node for node in scene.walk() if node.key == "scale-card")
    label_node = next(node for node in scene.walk() if node.key == "scale-label")
    assert card_node.bounds == Rect(150.0, 125.0, 100.0, 50.0)
    assert label_node.bounds == Rect(160.0, 135.0, 50.0, 15.0)
    assert label_node.font_size == pytest.approx(authored_font_size * 0.5)
    assert card.bounds == authored_card_bounds
    assert label.bounds == authored_label_bounds

    transition.advance(0.5)
    assert card.visual_scale == pytest.approx(0.75)
    transition.restore()
    assert card.visual_scale == pytest.approx(1.0)
    assert card.bounds == authored_card_bounds


def test_fade_slide_and_scale_are_frame_partition_independent_and_composable() -> None:
    direct = _button()
    partitioned = _button()
    direct_group = AnimationParallel(
        FadeTransition(direct, from_opacity=0.0, duration=1.0, easing=linear),
        SlideTransition(
            direct,
            from_offset=Point(64.0, 0.0),
            duration=1.0,
            easing=linear,
        ),
        ScaleTransition(direct, from_scale=0.8, duration=1.0, easing=linear),
    ).start()
    partitioned_group = AnimationParallel(
        FadeTransition(partitioned, from_opacity=0.0, duration=1.0, easing=linear),
        SlideTransition(
            partitioned,
            from_offset=Point(64.0, 0.0),
            duration=1.0,
            easing=linear,
        ),
        ScaleTransition(partitioned, from_scale=0.8, duration=1.0, easing=linear),
    ).start()

    direct_group.advance(0.625)
    for delta in (0.1, 0.2, 0.075, 0.25):
        partitioned_group.advance(delta)

    assert direct.opacity == pytest.approx(partitioned.opacity)
    assert direct.visual_offset == partitioned.visual_offset
    assert direct.visual_scale == pytest.approx(partitioned.visual_scale)
    assert direct.bounds == partitioned.bounds


def test_cancel_retains_sample_until_explicit_restore() -> None:
    button = _button()
    fade = FadeTransition(button, from_opacity=0.0, duration=1.0, easing=linear).start()
    fade.advance(0.25)
    sampled_opacity = button.opacity

    assert fade.cancel() is True
    assert fade.advance(0.5) == pytest.approx(0.5)
    assert button.opacity == pytest.approx(sampled_opacity)

    fade.restore()
    assert button.opacity == pytest.approx(0.8)


def test_visual_transitions_validate_endpoints() -> None:
    button = _button()

    with pytest.raises(ValueError, match="duration"):
        FadeTransition(button, duration=-0.01)
    with pytest.raises(ValueError, match="from_opacity"):
        FadeTransition(button, from_opacity=1.1)
    with pytest.raises(ValueError, match="to_opacity"):
        FadeTransition(button, to_opacity=math.nan)
    with pytest.raises(ValueError, match="from_offset"):
        SlideTransition(button, from_offset=Point(math.inf, 0.0))
    with pytest.raises(ValueError, match="to_offset"):
        SlideTransition(button, to_offset=Point(0.0, math.nan))
    with pytest.raises(ValueError, match="from_scale"):
        ScaleTransition(button, from_scale=0.0)
    with pytest.raises(ValueError, match="to_scale"):
        ScaleTransition(button, to_scale=math.inf)
    with pytest.raises(ValueError, match="visual_scale"):
        button.visual_scale = -1.0
