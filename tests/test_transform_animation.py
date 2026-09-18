from __future__ import annotations

import math

import pytest

from swirui import Button, FadeTransition, ScaleTransition, SlideTransition, linear
from swirui.rendering import Point, Rect
from swirui.widgets.runtime import compile_component_scene


def _scene_for(button: Button):
    scene = compile_component_scene(button, width=320.0, height=220.0)
    assert scene is not None
    return scene


def test_visual_scale_compiles_complete_subtree_without_mutating_layout() -> None:
    button = Button(
        "Scale",
        key="scale-button",
        bounds=Rect(20.0, 30.0, 120.0, 40.0),
        corner_radius=10.0,
        font_size=16.0,
    )
    authored_bounds = button.bounds
    authored_preferred = button.preferred_size

    button.visual_scale = 0.5
    scene = _scene_for(button)
    root = scene.root
    content = next(node for node in scene.walk() if node.key == "scale-button:content")

    assert root.bounds == Rect(50.0, 40.0, 60.0, 20.0)
    assert root.corner_radius.top_left == pytest.approx(5.0)
    assert content.bounds == Rect(56.0, 45.0, 48.0, 10.0)
    assert content.font_size == pytest.approx(8.0)
    assert button.bounds == authored_bounds
    assert button.preferred_size == authored_preferred

    assert scene.hit_test(Point(80.0, 50.0)) is root
    assert scene.hit_test(Point(25.0, 35.0)) is None


def test_visual_scale_composes_before_visual_offset() -> None:
    button = Button("Move", key="move", bounds=Rect(20.0, 20.0, 100.0, 40.0))
    button.visual_scale = 0.5
    button.set_visual_offset(12.0, -4.0)

    scene = _scene_for(button)

    assert scene.root.bounds == Rect(57.0, 26.0, 50.0, 20.0)
    assert button.bounds == Rect(20.0, 20.0, 100.0, 40.0)


def test_zero_visual_scale_hides_subtree_from_hit_testing() -> None:
    button = Button("Hidden", key="hidden", bounds=Rect(20.0, 20.0, 100.0, 40.0))
    button.visual_scale = 0.0

    scene = _scene_for(button)

    assert scene.root.opacity == 0.0
    assert scene.hit_test(Point(40.0, 30.0)) is None


def test_visual_scale_validation() -> None:
    button = Button("Scale", bounds=Rect(0.0, 0.0, 100.0, 40.0))

    with pytest.raises(ValueError, match="visual_scale"):
        button.visual_scale = -0.01
    with pytest.raises(ValueError, match="visual_scale"):
        button.visual_scale = math.nan
    with pytest.raises(ValueError, match="visual_scale"):
        button.visual_scale = math.inf


def test_fade_slide_and_scale_transitions_sample_visual_only_state() -> None:
    fade_widget = Button("Fade", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    fade = FadeTransition(fade_widget, 0.2, duration=1.0, easing=linear).start()
    assert fade.advance(0.5) == pytest.approx(0.0)
    assert fade_widget.opacity == pytest.approx(0.6)
    assert fade_widget.bounds == Rect(0.0, 0.0, 100.0, 40.0)

    slide_widget = Button("Slide", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    slide_widget.set_visual_offset(5.0, 7.0)
    slide = SlideTransition(
        slide_widget,
        Point(5.0, 27.0),
        duration=1.0,
        easing=linear,
    ).start()
    slide.advance(0.5)
    assert slide_widget.visual_offset == Point(5.0, 17.0)
    assert slide_widget.bounds == Rect(0.0, 0.0, 100.0, 40.0)

    scale_widget = Button("Scale", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    scale = ScaleTransition(scale_widget, 0.5, duration=1.0, easing=linear).start()
    scale.advance(0.5)
    assert scale_widget.visual_scale == pytest.approx(0.75)
    assert scale_widget.bounds == Rect(0.0, 0.0, 100.0, 40.0)


def test_scale_transition_is_frame_partition_independent_and_restorable() -> None:
    first = Button("A", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    second = Button("B", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    first_transition = ScaleTransition(first, 1.8, duration=1.0).start()
    second_transition = ScaleTransition(second, 1.8, duration=1.0).start()

    first_transition.advance(0.4)
    for _ in range(8):
        second_transition.advance(0.05)

    assert first.visual_scale == pytest.approx(second.visual_scale)
    sampled = first.visual_scale
    assert first_transition.cancel() is True
    assert first.visual_scale == pytest.approx(sampled)
    first_transition.restore()
    assert first.visual_scale == pytest.approx(1.0)


def test_transition_target_validation() -> None:
    button = Button("Validate", bounds=Rect(0.0, 0.0, 100.0, 40.0))

    with pytest.raises(ValueError, match="to_opacity"):
        FadeTransition(button, 1.1)
    with pytest.raises(ValueError, match="to_offset"):
        SlideTransition(button, Point(math.nan, 0.0))
    with pytest.raises(ValueError, match="to_scale"):
        ScaleTransition(button, -1.0)
