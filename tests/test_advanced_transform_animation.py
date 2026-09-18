from __future__ import annotations

import math

import pytest

from swirui import Button, FlipTransition, MorphTransition, RevealTransition, linear
from swirui.rendering import Point, Rect
from swirui.widgets.runtime import compile_component_scene


def _scene_for(button: Button):
    scene = compile_component_scene(button, width=640.0, height=420.0)
    assert scene is not None
    return scene


def _visual_center(button: Button) -> Point:
    return Point(
        button.bounds.x + button.bounds.width * 0.5 + button.visual_offset.x,
        button.bounds.y + button.bounds.height * 0.5 + button.visual_offset.y,
    )


def test_reveal_transition_preserves_authored_layout_and_restores_visual_state() -> None:
    button = Button("Reveal", bounds=Rect(40.0, 50.0, 180.0, 60.0), opacity=0.8)
    button.visual_scale = 1.25
    authored_bounds = button.bounds
    authored_preferred = button.preferred_size

    transition = RevealTransition(
        button,
        from_scale=0.8,
        from_opacity=0.25,
        duration=1.0,
        easing=linear,
    ).start()

    assert button.visual_scale == pytest.approx(1.0)
    assert button.opacity == pytest.approx(0.2)

    transition.advance(0.5)
    assert button.visual_scale == pytest.approx(1.125)
    assert button.opacity == pytest.approx(0.5)
    assert button.bounds == authored_bounds
    assert button.preferred_size == authored_preferred

    transition.advance(0.5)
    assert button.visual_scale == pytest.approx(1.25)
    assert button.opacity == pytest.approx(0.8)
    transition.restore()
    assert button.visual_scale == pytest.approx(1.25)
    assert button.opacity == pytest.approx(0.8)


def test_flip_transition_collapses_at_midpoint_and_swaps_once() -> None:
    button = Button("Front", bounds=Rect(20.0, 20.0, 160.0, 56.0))
    button.visual_scale = 1.2
    midpoint_calls: list[float] = []

    transition = FlipTransition(
        button,
        duration=1.0,
        easing=linear,
        on_midpoint=lambda: midpoint_calls.append(button.visual_scale),
    ).start()

    transition.advance(0.5)
    assert midpoint_calls == [pytest.approx(0.0)]
    assert button.visual_scale == pytest.approx(0.0)
    assert _scene_for(button).hit_test(Point(100.0, 48.0)) is None

    transition.advance(0.25)
    assert len(midpoint_calls) == 1
    assert button.visual_scale == pytest.approx(0.6)

    transition.advance(0.25)
    assert len(midpoint_calls) == 1
    assert button.visual_scale == pytest.approx(1.2)

    transition.start()
    transition.advance(0.75)
    assert len(midpoint_calls) == 2
    transition.restore()
    assert button.visual_scale == pytest.approx(1.2)


def test_flip_transition_large_frame_crosses_midpoint_once() -> None:
    button = Button("Flip", bounds=Rect(0.0, 0.0, 120.0, 48.0))
    midpoint_calls = 0

    def swap() -> None:
        nonlocal midpoint_calls
        midpoint_calls += 1

    transition = FlipTransition(
        button,
        duration=1.0,
        easing=linear,
        on_midpoint=swap,
    ).start()
    transition.advance(0.8)

    assert midpoint_calls == 1
    assert button.visual_scale == pytest.approx(0.6)


def test_morph_transition_aligns_centers_scales_and_crossfades() -> None:
    source = Button(
        "Source",
        bounds=Rect(20.0, 30.0, 100.0, 50.0),
        opacity=0.8,
    )
    target = Button(
        "Target",
        bounds=Rect(300.0, 170.0, 200.0, 100.0),
        opacity=0.6,
    )
    source.set_visual_offset(4.0, -2.0)
    target.set_visual_offset(-6.0, 8.0)
    source_bounds = source.bounds
    target_bounds = target.bounds

    transition = MorphTransition(source, target, duration=1.0, easing=linear).start()

    assert source.visual_scale == pytest.approx(1.0)
    assert target.visual_scale == pytest.approx(0.5)
    assert source.opacity == pytest.approx(0.8)
    assert target.opacity == pytest.approx(0.0)
    assert _visual_center(source) == _visual_center(target)

    transition.advance(0.5)
    assert source.visual_scale == pytest.approx(1.5)
    assert target.visual_scale == pytest.approx(0.75)
    assert source.opacity == pytest.approx(0.4)
    assert target.opacity == pytest.approx(0.3)
    source_center = _visual_center(source)
    target_center = _visual_center(target)
    assert source_center.x == pytest.approx(target_center.x)
    assert source_center.y == pytest.approx(target_center.y)
    assert source.bounds == source_bounds
    assert target.bounds == target_bounds

    transition.advance(0.5)
    assert source.visual_scale == pytest.approx(2.0)
    assert target.visual_scale == pytest.approx(1.0)
    assert source.opacity == pytest.approx(0.0)
    assert target.opacity == pytest.approx(0.6)
    assert _visual_center(source) == _visual_center(target)

    transition.restore()
    assert source.visual_scale == pytest.approx(1.0)
    assert target.visual_scale == pytest.approx(1.0)
    assert source.opacity == pytest.approx(0.8)
    assert target.opacity == pytest.approx(0.6)
    assert source.visual_offset == Point(4.0, -2.0)
    assert target.visual_offset == Point(-6.0, 8.0)


def test_morph_transition_is_frame_partition_independent() -> None:
    source_a = Button("A", bounds=Rect(0.0, 0.0, 100.0, 50.0))
    target_a = Button("B", bounds=Rect(300.0, 200.0, 200.0, 100.0))
    source_b = Button("C", bounds=Rect(0.0, 0.0, 100.0, 50.0))
    target_b = Button("D", bounds=Rect(300.0, 200.0, 200.0, 100.0))

    first = MorphTransition(source_a, target_a, duration=1.0).start()
    second = MorphTransition(source_b, target_b, duration=1.0).start()

    first.advance(0.4)
    for _ in range(8):
        second.advance(0.05)

    assert source_a.visual_scale == pytest.approx(source_b.visual_scale)
    assert target_a.visual_scale == pytest.approx(target_b.visual_scale)
    assert source_a.visual_offset.x == pytest.approx(source_b.visual_offset.x)
    assert source_a.visual_offset.y == pytest.approx(source_b.visual_offset.y)
    assert target_a.opacity == pytest.approx(target_b.opacity)


def test_advanced_transform_validation_is_strict() -> None:
    button = Button("Validate", bounds=Rect(0.0, 0.0, 100.0, 50.0))

    with pytest.raises(ValueError, match="from_opacity"):
        RevealTransition(button, from_opacity=1.1)
    with pytest.raises(ValueError, match="from_scale"):
        RevealTransition(button, from_scale=math.nan)
    with pytest.raises(ValueError, match="distinct"):
        MorphTransition(button, button)

    mismatched = Button("Wide", bounds=Rect(0.0, 0.0, 180.0, 50.0))
    with pytest.raises(ValueError, match="matching visual aspect ratios"):
        MorphTransition(button, mismatched)

    collapsed = Button("Collapsed", bounds=Rect(0.0, 0.0, 100.0, 50.0))
    collapsed.visual_scale = 0.0
    with pytest.raises(ValueError, match="greater than zero"):
        MorphTransition(collapsed, button)
