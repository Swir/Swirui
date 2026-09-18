from __future__ import annotations

import math

import pytest

from swirui import AnimationSequence, AnimationStatus, Keyframe, KeyframeAnimation, linear


def test_keyframe_animation_samples_uneven_segments_deterministically() -> None:
    samples: list[float] = []
    animation = KeyframeAnimation(
        (
            Keyframe(0.0, 0.0, linear),
            Keyframe(0.25, 100.0, linear),
            Keyframe(1.0, 40.0, linear),
        ),
        2.0,
        samples.append,
    ).start()

    assert samples == [0.0]
    animation.advance(0.25)
    assert animation.progress == pytest.approx(0.125)
    assert animation.value == pytest.approx(50.0)

    animation.advance(0.75)
    assert animation.progress == pytest.approx(0.5)
    assert animation.value == pytest.approx(80.0)

    tail = animation.advance(1.25)
    assert tail == pytest.approx(0.25)
    assert animation.status is AnimationStatus.COMPLETED
    assert animation.value == pytest.approx(40.0)
    assert samples[-1] == pytest.approx(40.0)


def test_keyframe_animation_uses_easing_from_segment_start() -> None:
    animation = KeyframeAnimation(
        (
            Keyframe(0.0, 10.0, lambda progress: progress * progress),
            Keyframe(0.5, 30.0, linear),
            Keyframe(1.0, 50.0, linear),
        ),
        1.0,
        lambda _value: None,
    )

    assert animation.value_at(0.25) == pytest.approx(15.0)
    assert animation.value_at(0.75) == pytest.approx(40.0)


def test_keyframe_animation_is_frame_partition_independent() -> None:
    frames = (
        Keyframe(0.0, -20.0, linear),
        Keyframe(0.3, 80.0, linear),
        Keyframe(0.7, 10.0, linear),
        Keyframe(1.0, 60.0, linear),
    )
    coarse = KeyframeAnimation(frames, 1.2, lambda _value: None).start()
    fine = KeyframeAnimation(frames, 1.2, lambda _value: None).start()

    coarse.advance(0.72)
    for _ in range(12):
        fine.advance(0.06)

    assert coarse.elapsed == pytest.approx(fine.elapsed)
    assert coarse.progress == pytest.approx(fine.progress)
    assert coarse.value == pytest.approx(fine.value)


def test_keyframe_animation_cancel_restart_and_sequence_tail() -> None:
    completed: list[str] = []
    first = KeyframeAnimation(
        (Keyframe(0.0, 0.0), Keyframe(1.0, 1.0)),
        0.25,
        lambda _value: None,
        on_complete=lambda: completed.append("first"),
    ).start()
    first.advance(0.1)
    cancelled_value = first.value
    assert first.cancel() is True
    assert first.status is AnimationStatus.CANCELLED
    assert first.value == pytest.approx(cancelled_value)
    assert first.cancel() is False

    first.start()
    second_values: list[float] = []
    second = KeyframeAnimation(
        (Keyframe(0.0, 10.0), Keyframe(1.0, 20.0)),
        0.25,
        second_values.append,
    )
    sequence = AnimationSequence(first, second).start()
    tail = sequence.advance(0.6)

    assert tail == pytest.approx(0.1)
    assert sequence.status is AnimationStatus.COMPLETED
    assert completed == ["first"]
    assert second_values[-1] == pytest.approx(20.0)


def test_zero_duration_keyframes_complete_on_start_once() -> None:
    samples: list[float] = []
    completed: list[bool] = []
    animation = KeyframeAnimation(
        (Keyframe(0.0, 2.0), Keyframe(0.5, 8.0), Keyframe(1.0, 5.0)),
        0.0,
        samples.append,
        on_complete=lambda: completed.append(True),
    ).start()

    assert animation.status is AnimationStatus.COMPLETED
    assert animation.progress == pytest.approx(1.0)
    assert animation.value == pytest.approx(5.0)
    assert samples == [2.0, 5.0]
    assert completed == [True]


def test_keyframe_validation_rejects_ambiguous_timelines() -> None:
    with pytest.raises(ValueError, match="at least two"):
        KeyframeAnimation((Keyframe(0.0, 1.0),), 1.0, lambda _value: None)
    with pytest.raises(ValueError, match="first keyframe"):
        KeyframeAnimation(
            (Keyframe(0.1, 1.0), Keyframe(1.0, 2.0)),
            1.0,
            lambda _value: None,
        )
    with pytest.raises(ValueError, match="last keyframe"):
        KeyframeAnimation(
            (Keyframe(0.0, 1.0), Keyframe(0.9, 2.0)),
            1.0,
            lambda _value: None,
        )
    with pytest.raises(ValueError, match="increase strictly"):
        KeyframeAnimation(
            (
                Keyframe(0.0, 1.0),
                Keyframe(0.5, 2.0),
                Keyframe(0.5, 3.0),
                Keyframe(1.0, 4.0),
            ),
            1.0,
            lambda _value: None,
        )
    with pytest.raises(ValueError, match="duration"):
        KeyframeAnimation(
            (Keyframe(0.0, 1.0), Keyframe(1.0, 2.0)),
            math.inf,
            lambda _value: None,
        )
    with pytest.raises(ValueError, match="offset"):
        Keyframe(math.nan, 1.0)
    with pytest.raises(ValueError, match="value"):
        Keyframe(0.5, math.inf)


def test_sampling_rejects_invalid_progress_and_non_finite_easing() -> None:
    animation = KeyframeAnimation(
        (Keyframe(0.0, 0.0, lambda _progress: math.nan), Keyframe(1.0, 1.0)),
        1.0,
        lambda _value: None,
    )
    with pytest.raises(ValueError, match="progress"):
        animation.value_at(-0.1)
    with pytest.raises(ValueError, match="easing result"):
        animation.value_at(0.5)
