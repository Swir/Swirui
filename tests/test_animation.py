from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationController,
    AnimationHandle,
    AnimationSequence,
    AnimationStatus,
    Button,
    Tween,
    animate_bounds,
    animate_opacity,
    ease_in_out_cubic,
    linear,
)
from swirui.rendering import Rect


def test_tween_validation_and_easing_endpoints() -> None:
    values: list[float] = []

    with pytest.raises(ValueError, match="duration"):
        Tween(0.0, 1.0, 0.0, values.append)
    with pytest.raises(ValueError, match="finite"):
        Tween(0.0, math.inf, 1.0, values.append)
    with pytest.raises(ValueError, match="delay"):
        Tween(0.0, 1.0, 1.0, values.append, delay=-0.1)

    tween = Tween(10.0, 20.0, 2.0, values.append, easing=ease_in_out_cubic)
    assert tween.value_at(-1.0) == pytest.approx(10.0)
    assert tween.value_at(0.5) == pytest.approx(15.0)
    assert tween.value_at(2.0) == pytest.approx(20.0)


def test_absolute_timing_is_frame_rate_independent() -> None:
    sixty_hz: list[float] = []
    sparse: list[float] = []

    first = AnimationHandle(AnimationSequence((Tween(0.0, 100.0, 1.0, sixty_hz.append),)))
    second = AnimationHandle(AnimationSequence((Tween(0.0, 100.0, 1.0, sparse.append),)))
    first.start(10.0)
    second.start(10.0)

    for frame in range(1, 61):
        first.tick(10.0 + frame / 60.0)
    second.tick(10.17)
    second.tick(10.73)
    second.tick(11.0)

    assert first.status is AnimationStatus.COMPLETED
    assert second.status is AnimationStatus.COMPLETED
    assert sixty_hz[-1] == pytest.approx(100.0)
    assert sparse[-1] == pytest.approx(100.0)
    assert second.tick(12.0) is False


def test_chained_tweens_catch_up_across_delayed_frames() -> None:
    first_values: list[float] = []
    second_values: list[float] = []
    sequence = Tween(0.0, 10.0, 1.0, first_values.append, easing=linear).then(
        Tween(50.0, 100.0, 2.0, second_values.append, easing=linear, delay=0.5)
    )
    handle = AnimationHandle(sequence).start(5.0)

    handle.tick(6.0)
    assert handle.current_index == 1
    assert first_values[-1] == pytest.approx(10.0)
    assert second_values[-1] == pytest.approx(50.0)

    handle.tick(7.5)
    assert second_values[-1] == pytest.approx(75.0)

    handle.tick(8.5)
    assert handle.completed is True
    assert second_values[-1] == pytest.approx(100.0)


def test_cancellation_can_hold_or_apply_final_value() -> None:
    values: list[float] = []
    handle = AnimationHandle(AnimationSequence((Tween(0.0, 1.0, 1.0, values.append),)))
    handle.start(0.0)
    handle.tick(0.25)
    before_cancel = values[-1]

    assert handle.cancel() is True
    assert handle.cancelled is True
    assert values[-1] == before_cancel
    assert handle.cancel() is False

    values.clear()
    handle.start(0.0)
    assert handle.cancel(apply_final_value=True) is True
    assert values[-1] == pytest.approx(1.0)


def test_controller_runs_independent_sequences_and_prunes_finished_handles() -> None:
    left: list[float] = []
    right: list[float] = []
    controller = AnimationController()

    left_handle = controller.play(Tween(0.0, 1.0, 1.0, left.append), start_time=20.0)
    right_handle = controller.play(Tween(10.0, 20.0, 2.0, right.append), start_time=20.0)

    assert controller.active is True
    assert len(controller.handles) == 2
    assert controller.tick(21.0) is True
    assert left_handle.completed is True
    assert right_handle.running is True
    assert controller.handles == (right_handle,)

    controller.tick(22.0)
    assert controller.active is False
    assert controller.handles == ()
    assert right[-1] == pytest.approx(20.0)


def test_widget_opacity_and_bounds_helpers_use_retained_properties() -> None:
    button = Button("Animate", bounds=Rect(10.0, 20.0, 120.0, 44.0), opacity=1.0)
    controller = AnimationController()

    controller.play(
        animate_opacity(button, 0.25, duration=1.0, easing=linear),
        start_time=0.0,
    )
    controller.tick(0.5)
    assert button.opacity == pytest.approx(0.625)
    controller.tick(1.0)
    assert button.opacity == pytest.approx(0.25)

    controller.play(
        animate_bounds(
            button,
            Rect(30.0, 60.0, 200.0, 80.0),
            duration=2.0,
            easing=linear,
        ),
        start_time=2.0,
    )
    controller.tick(3.0)
    assert button.bounds == Rect(20.0, 40.0, 160.0, 62.0)
    controller.tick(4.0)
    assert button.bounds == Rect(30.0, 60.0, 200.0, 80.0)


def test_monotonic_tick_guard_prevents_time_reversal() -> None:
    values: list[float] = []
    handle = AnimationHandle(AnimationSequence((Tween(0.0, 1.0, 1.0, values.append),)))
    handle.start(100.0)
    handle.tick(100.5)

    with pytest.raises(ValueError, match="monotonic"):
        handle.tick(100.4)
