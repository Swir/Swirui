from __future__ import annotations

import math

import pytest

from swirui import Button, PageTransition, PageTransitionDirection, linear
from swirui.rendering import Point, Rect


def _pages() -> tuple[Button, Button]:
    outgoing = Button("Old", bounds=Rect(20.0, 30.0, 220.0, 64.0), opacity=0.8)
    incoming = Button("New", bounds=Rect(20.0, 30.0, 220.0, 64.0), opacity=0.6)
    outgoing.visual_offset = Point(3.0, 5.0)
    incoming.visual_offset = Point(-2.0, 7.0)
    return outgoing, incoming


def test_page_transition_crossfades_and_slides_without_layout_changes() -> None:
    outgoing, incoming = _pages()
    outgoing_bounds = outgoing.bounds
    incoming_bounds = incoming.bounds
    transition = PageTransition(
        outgoing,
        incoming,
        duration=1.0,
        distance=40.0,
        direction=PageTransitionDirection.LEFT,
        easing=linear,
    ).start()

    assert outgoing.opacity == pytest.approx(0.8)
    assert incoming.opacity == pytest.approx(0.0)
    assert outgoing.visual_offset == Point(3.0, 5.0)
    assert incoming.visual_offset == Point(38.0, 7.0)

    transition.advance(0.5)

    assert outgoing.opacity == pytest.approx(0.4)
    assert incoming.opacity == pytest.approx(0.3)
    assert outgoing.visual_offset == Point(-17.0, 5.0)
    assert incoming.visual_offset == Point(18.0, 7.0)
    assert outgoing.bounds == outgoing_bounds
    assert incoming.bounds == incoming_bounds

    assert transition.advance(0.75) == pytest.approx(0.25)
    assert outgoing.opacity == pytest.approx(0.0)
    assert incoming.opacity == pytest.approx(0.6)
    assert outgoing.visual_offset == Point(-37.0, 5.0)
    assert incoming.visual_offset == Point(-2.0, 7.0)


def test_page_transition_is_frame_partition_independent() -> None:
    outgoing_a, incoming_a = _pages()
    outgoing_b, incoming_b = _pages()
    direct = PageTransition(outgoing_a, incoming_a, duration=1.0, easing=linear).start()
    partitioned = PageTransition(outgoing_b, incoming_b, duration=1.0, easing=linear).start()

    direct.advance(0.625)
    for delta in (0.1, 0.2, 0.075, 0.25):
        partitioned.advance(delta)

    assert direct.elapsed == pytest.approx(partitioned.elapsed)
    assert direct.progress == pytest.approx(partitioned.progress)
    assert outgoing_a.opacity == pytest.approx(outgoing_b.opacity)
    assert incoming_a.opacity == pytest.approx(incoming_b.opacity)
    assert outgoing_a.visual_offset == outgoing_b.visual_offset
    assert incoming_a.visual_offset == incoming_b.visual_offset


@pytest.mark.parametrize(
    ("direction", "expected_outgoing", "expected_incoming_start"),
    [
        (PageTransitionDirection.LEFT, Point(-20.0, 0.0), Point(20.0, 0.0)),
        (PageTransitionDirection.RIGHT, Point(20.0, 0.0), Point(-20.0, 0.0)),
        (PageTransitionDirection.UP, Point(0.0, -20.0), Point(0.0, 20.0)),
        (PageTransitionDirection.DOWN, Point(0.0, 20.0), Point(0.0, -20.0)),
    ],
)
def test_page_transition_direction_vectors(
    direction: PageTransitionDirection,
    expected_outgoing: Point,
    expected_incoming_start: Point,
) -> None:
    outgoing = Button("Old", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    incoming = Button("New", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    transition = PageTransition(
        outgoing,
        incoming,
        duration=1.0,
        distance=20.0,
        direction=direction,
        easing=linear,
    ).start()

    assert incoming.visual_offset == expected_incoming_start
    transition.advance(1.0)
    assert outgoing.visual_offset == expected_outgoing
    assert incoming.visual_offset == Point()


def test_page_transition_cancel_retains_current_sample_and_restore_resets_authored_state() -> None:
    outgoing, incoming = _pages()
    transition = PageTransition(outgoing, incoming, duration=1.0, easing=linear).start()
    transition.advance(0.25)
    sampled = (
        outgoing.opacity,
        incoming.opacity,
        outgoing.visual_offset,
        incoming.visual_offset,
    )

    assert transition.cancel() is True
    assert transition.advance(0.5) == pytest.approx(0.5)
    assert sampled == (
        outgoing.opacity,
        incoming.opacity,
        outgoing.visual_offset,
        incoming.visual_offset,
    )

    transition.restore()
    assert outgoing.opacity == pytest.approx(0.8)
    assert incoming.opacity == pytest.approx(0.6)
    assert outgoing.visual_offset == Point(3.0, 5.0)
    assert incoming.visual_offset == Point(-2.0, 7.0)


def test_page_transition_validates_inputs() -> None:
    outgoing, incoming = _pages()

    with pytest.raises(ValueError, match="distinct"):
        PageTransition(outgoing, outgoing)
    with pytest.raises(ValueError, match="duration"):
        PageTransition(outgoing, incoming, duration=-0.01)
    with pytest.raises(ValueError, match="distance"):
        PageTransition(outgoing, incoming, distance=math.nan)
