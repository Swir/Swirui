from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationSequence,
    AnimationStatus,
    DelayAnimation,
    RepeatAnimation,
    Tween,
)


def test_delay_carries_frame_tail_and_completes_once() -> None:
    completions: list[str] = []
    delay = DelayAnimation(0.25, on_complete=lambda: completions.append("done")).start()

    assert delay.advance(0.1) == 0.0
    assert delay.elapsed == pytest.approx(0.1)
    assert delay.progress == pytest.approx(0.4)

    tail = delay.advance(0.3)
    assert tail == pytest.approx(0.15)
    assert delay.status is AnimationStatus.COMPLETED
    assert delay.progress == 1.0
    assert completions == ["done"]

    assert delay.advance(1.0) == 1.0
    assert completions == ["done"]


def test_zero_duration_delay_composes_without_losing_frame_time() -> None:
    samples: list[float] = []
    sequence = AnimationSequence(
        DelayAnimation(0.0),
        Tween(0.0, 10.0, 0.5, samples.append),
    ).start()

    tail = sequence.advance(0.25)

    assert tail == 0.0
    assert sequence.status is AnimationStatus.RUNNING
    assert samples[-1] == pytest.approx(5.0)


def test_delay_cancellation_and_restart_are_deterministic() -> None:
    delay = DelayAnimation(1.0).start()
    delay.advance(0.3)

    assert delay.cancel() is True
    assert delay.cancel() is False
    assert delay.elapsed == pytest.approx(0.3)
    assert delay.advance(0.5) == 0.5

    delay.start()
    assert delay.status is AnimationStatus.RUNNING
    assert delay.elapsed == 0.0


def test_repeat_animation_carries_tail_across_iterations() -> None:
    samples: list[float] = []
    completions: list[str] = []
    repeat = RepeatAnimation(
        Tween(0.0, 1.0, 0.25, samples.append),
        3,
        on_complete=lambda: completions.append("repeat"),
    ).start()

    tail = repeat.advance(0.8)

    assert tail == pytest.approx(0.05)
    assert repeat.completed_iterations == 3
    assert repeat.status is AnimationStatus.COMPLETED
    assert completions == ["repeat"]
    assert samples == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_repeat_animation_is_frame_partition_independent() -> None:
    coarse_samples: list[float] = []
    fine_samples: list[float] = []
    coarse = RepeatAnimation(Tween(0.0, 1.0, 0.2, coarse_samples.append), 3).start()
    fine = RepeatAnimation(Tween(0.0, 1.0, 0.2, fine_samples.append), 3).start()

    coarse.advance(0.35)
    for _ in range(7):
        fine.advance(0.05)

    assert coarse.status is AnimationStatus.RUNNING
    assert fine.status is AnimationStatus.RUNNING
    assert coarse.completed_iterations == fine.completed_iterations == 1
    assert coarse_samples[-1] == pytest.approx(fine_samples[-1])
    assert coarse_samples[-1] == pytest.approx(0.75)


def test_repeat_animation_handles_zero_duration_children_without_looping_forever() -> None:
    samples: list[float] = []
    repeat = RepeatAnimation(Tween(2.0, 4.0, 0.0, samples.append), 4).start()

    assert repeat.status is AnimationStatus.COMPLETED
    assert repeat.completed_iterations == 4
    assert samples == [2.0, 4.0] * 4
    assert repeat.advance(0.5) == 0.5


def test_repeat_animation_cancellation_stops_the_active_child() -> None:
    child = Tween(0.0, 1.0, 1.0, lambda _value: None)
    repeat = RepeatAnimation(child, 5).start()
    repeat.advance(0.2)

    assert repeat.cancel() is True
    assert repeat.cancel() is False
    assert repeat.status is AnimationStatus.CANCELLED
    assert child.status is AnimationStatus.CANCELLED
    assert repeat.completed_iterations == 0
    assert repeat.advance(0.5) == 0.5


def test_timeline_helpers_validate_inputs() -> None:
    with pytest.raises(ValueError, match="duration"):
        DelayAnimation(-0.1)
    with pytest.raises(ValueError, match="duration"):
        DelayAnimation(math.inf)
    with pytest.raises(ValueError, match="count"):
        RepeatAnimation(Tween(0.0, 1.0, 1.0, lambda _value: None), 0)
    with pytest.raises(ValueError, match="count"):
        RepeatAnimation(Tween(0.0, 1.0, 1.0, lambda _value: None), True)  # type: ignore[arg-type]

    delay = DelayAnimation(1.0).start()
    with pytest.raises(ValueError, match="delta_seconds"):
        delay.advance(math.nan)

    repeat = RepeatAnimation(Tween(0.0, 1.0, 1.0, lambda _value: None), 2).start()
    with pytest.raises(ValueError, match="delta_seconds"):
        repeat.advance(-0.01)
