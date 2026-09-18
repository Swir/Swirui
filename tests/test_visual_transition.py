from __future__ import annotations

import math

import pytest

from swirui import AnimationParallel, Button, FadeTransition, SlideTransition, linear
from swirui.rendering import Point, Rect


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


def test_fade_and_slide_are_frame_partition_independent_and_composable() -> None:
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
    ).start()
    partitioned_group = AnimationParallel(
        FadeTransition(partitioned, from_opacity=0.0, duration=1.0, easing=linear),
        SlideTransition(
            partitioned,
            from_offset=Point(64.0, 0.0),
            duration=1.0,
            easing=linear,
        ),
    ).start()

    direct_group.advance(0.625)
    for delta in (0.1, 0.2, 0.075, 0.25):
        partitioned_group.advance(delta)

    assert direct.opacity == pytest.approx(partitioned.opacity)
    assert direct.visual_offset == partitioned.visual_offset
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
