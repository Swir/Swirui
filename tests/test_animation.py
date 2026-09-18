from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationController,
    AnimationSequence,
    AnimationStatus,
    App,
    State,
    Tween,
    Window,
    ease_in_out_cubic,
    tween_state,
)
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


def test_tween_progress_depends_on_elapsed_time_not_step_count() -> None:
    one_step: list[float] = []
    many_steps: list[float] = []
    direct = Tween(0.0, 10.0, 1.0, one_step.append).start()
    sliced = Tween(0.0, 10.0, 1.0, many_steps.append).start()

    direct.advance(0.5)
    for _ in range(5):
        sliced.advance(0.1)

    assert direct.progress == pytest.approx(0.5)
    assert sliced.progress == pytest.approx(0.5)
    assert one_step[-1] == pytest.approx(5.0)
    assert many_steps[-1] == pytest.approx(5.0)


def test_tween_completion_is_exact_and_callback_fires_once() -> None:
    values: list[float] = []
    completed: list[str] = []
    tween = Tween(
        2.0,
        8.0,
        0.25,
        values.append,
        easing=ease_in_out_cubic,
        on_complete=lambda: completed.append("done"),
    ).start()

    unused = tween.advance(0.4)
    tween.advance(1.0)

    assert unused == pytest.approx(0.15)
    assert values[-1] == 8.0
    assert tween.progress == 1.0
    assert tween.status is AnimationStatus.COMPLETED
    assert completed == ["done"]


def test_zero_duration_tween_completes_immediately() -> None:
    values: list[float] = []
    tween = Tween(4.0, 9.0, 0.0, values.append).start()

    assert values == [4.0, 9.0]
    assert tween.status is AnimationStatus.COMPLETED
    assert tween.progress == 1.0


def test_tween_rejects_invalid_time_and_non_finite_values() -> None:
    with pytest.raises(ValueError, match="duration"):
        Tween(0.0, 1.0, -0.1, lambda _value: None)
    with pytest.raises(ValueError, match="from_value"):
        Tween(math.nan, 1.0, 1.0, lambda _value: None)

    tween = Tween(0.0, 1.0, 1.0, lambda _value: None).start()
    with pytest.raises(ValueError, match="delta_seconds"):
        tween.advance(-0.01)


def test_sequence_carries_frame_tail_across_tweens() -> None:
    first_values: list[float] = []
    second_values: list[float] = []
    sequence = AnimationSequence(
        Tween(0.0, 10.0, 0.25, first_values.append),
        Tween(10.0, 20.0, 0.75, second_values.append),
    ).start()

    unused = sequence.advance(0.5)

    assert unused == 0.0
    assert first_values[-1] == 10.0
    assert second_values[-1] == pytest.approx(10.0 + 10.0 / 3.0)
    assert sequence.current_index == 1
    assert sequence.status is AnimationStatus.RUNNING


def test_sequence_chaining_and_cancellation_do_not_force_completion() -> None:
    values: list[float] = []
    completions: list[str] = []
    first = Tween(0.0, 1.0, 0.1, values.append)
    second = Tween(1.0, 2.0, 0.2, values.append, on_complete=lambda: completions.append("second"))
    sequence = first.then(second).start()

    sequence.advance(0.15)
    sampled = values[-1]
    assert sequence.cancel() is True
    assert sequence.cancel() is False
    sequence.advance(1.0)

    assert sequence.status is AnimationStatus.CANCELLED
    assert values[-1] == sampled
    assert completions == []


def test_tween_state_writes_reactive_samples() -> None:
    state = State(2.0)
    observed: list[float] = []
    state.subscribe(observed.append)
    tween = tween_state(state, 6.0, 1.0).start()

    tween.advance(0.25)
    tween.advance(0.75)

    assert state.value == 6.0
    assert observed == [3.0, 6.0]


def test_animation_controller_is_window_scoped_and_disposable() -> None:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    first_window = app.add_window(Window(title="Animated"))
    other_window = app.add_window(Window(title="Other"))
    values: list[float] = []
    tween = Tween(0.0, 10.0, 1.0, values.append)
    controller = AnimationController(app, first_window)

    controller.play(tween)
    app.emit("frame_rendered", window=other_window, frame_delta=0.5)
    assert values[-1] == 0.0

    app.emit("frame_rendered", window=first_window, frame_delta=0.25)
    assert values[-1] == pytest.approx(2.5)
    assert controller.active_count == 1

    controller.dispose()
    app.emit("frame_rendered", window=first_window, frame_delta=0.25)
    assert values[-1] == pytest.approx(2.5)
    assert tween.status is AnimationStatus.CANCELLED
    assert controller.active_count == 0


def test_controller_rejects_play_after_dispose() -> None:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window())
    controller = AnimationController(app, window)
    controller.dispose()

    with pytest.raises(RuntimeError, match="disposed"):
        controller.play(Tween(0.0, 1.0, 1.0, lambda _value: None))
