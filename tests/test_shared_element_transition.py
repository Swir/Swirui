from __future__ import annotations

import math

import pytest

from swirui import Button, SharedElementTransition, linear
from swirui.rendering import Point, Rect


def _elements() -> tuple[Button, Button]:
    source = Button("Source", bounds=Rect(10.0, 20.0, 100.0, 40.0), opacity=0.8)
    target = Button("Target", bounds=Rect(210.0, 120.0, 140.0, 80.0), opacity=0.6)
    source.visual_offset = Point(2.0, 3.0)
    target.visual_offset = Point(-4.0, 7.0)
    return source, target


def _visual_center(widget: Button) -> Point:
    return Point(
        widget.bounds.x + widget.bounds.width * 0.5 + widget.visual_offset.x,
        widget.bounds.y + widget.bounds.height * 0.5 + widget.visual_offset.y,
    )


def test_shared_element_transition_aligns_visual_centers_without_layout_mutation() -> None:
    source, target = _elements()
    source_bounds = source.bounds
    target_bounds = target.bounds
    transition = SharedElementTransition(source, target, duration=1.0, easing=linear).start()

    assert source.opacity == pytest.approx(0.8)
    assert target.opacity == pytest.approx(0.0)
    assert _visual_center(source) == _visual_center(target)
    assert source.bounds == source_bounds
    assert target.bounds == target_bounds

    transition.advance(0.5)

    assert source.opacity == pytest.approx(0.4)
    assert target.opacity == pytest.approx(0.3)
    assert _visual_center(source) == _visual_center(target)
    assert source.visual_offset == Point(109.0, 65.0)
    assert target.visual_offset == Point(-111.0, -55.0)
    assert source.bounds == source_bounds
    assert target.bounds == target_bounds

    assert transition.advance(0.75) == pytest.approx(0.25)
    assert source.opacity == pytest.approx(0.0)
    assert target.opacity == pytest.approx(0.6)
    assert source.visual_offset == Point(216.0, 127.0)
    assert target.visual_offset == Point(-4.0, 7.0)
    assert _visual_center(source) == _visual_center(target)


def test_shared_element_transition_is_frame_partition_independent() -> None:
    source_a, target_a = _elements()
    source_b, target_b = _elements()
    direct = SharedElementTransition(source_a, target_a, duration=1.0, easing=linear).start()
    partitioned = SharedElementTransition(source_b, target_b, duration=1.0, easing=linear).start()

    direct.advance(0.625)
    for delta in (0.1, 0.2, 0.075, 0.25):
        partitioned.advance(delta)

    assert direct.elapsed == pytest.approx(partitioned.elapsed)
    assert direct.progress == pytest.approx(partitioned.progress)
    assert source_a.opacity == pytest.approx(source_b.opacity)
    assert target_a.opacity == pytest.approx(target_b.opacity)
    assert source_a.visual_offset == source_b.visual_offset
    assert target_a.visual_offset == target_b.visual_offset


def test_shared_element_transition_cancel_and_restore_preserve_authored_state() -> None:
    source, target = _elements()
    transition = SharedElementTransition(source, target, duration=1.0, easing=linear).start()
    transition.advance(0.25)
    sampled = (
        source.opacity,
        target.opacity,
        source.visual_offset,
        target.visual_offset,
    )

    assert transition.cancel() is True
    assert transition.advance(0.5) == pytest.approx(0.5)
    assert sampled == (
        source.opacity,
        target.opacity,
        source.visual_offset,
        target.visual_offset,
    )

    transition.restore()
    assert source.opacity == pytest.approx(0.8)
    assert target.opacity == pytest.approx(0.6)
    assert source.visual_offset == Point(2.0, 3.0)
    assert target.visual_offset == Point(-4.0, 7.0)


def test_shared_element_transition_zero_duration_completes_immediately() -> None:
    source, target = _elements()
    transition = SharedElementTransition(source, target, duration=0.0, easing=linear).start()

    assert transition.progress == pytest.approx(1.0)
    assert source.opacity == pytest.approx(0.0)
    assert target.opacity == pytest.approx(0.6)
    assert target.visual_offset == Point(-4.0, 7.0)


def test_shared_element_transition_validates_inputs() -> None:
    source, target = _elements()

    with pytest.raises(ValueError, match="distinct"):
        SharedElementTransition(source, source)
    with pytest.raises(ValueError, match="duration"):
        SharedElementTransition(source, target, duration=-0.01)
    with pytest.raises(ValueError, match="duration"):
        SharedElementTransition(source, target, duration=math.nan)
