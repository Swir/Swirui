from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationController,
    AnimationParallel,
    AnimationSequence,
    AnimationStatus,
    App,
    DecayAnimation,
    SpringAnimation,
    State,
    Tween,
    Window,
    decay_state,
    ease_in_out_cubic,
    spring_state,
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
    second = Tween(
        1.0,
        2.0,
        0.2,
        values.append,
        on_complete=lambda: completions.append("second"),
    )
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


def test_spring_sampling_is_independent_of_frame_partition() -> None:
    direct_values: list[float] = []
    sliced_values: list[float] = []
    direct = SpringAnimation(
        0.0,
        100.0,
        direct_values.append,
        stiffness=180.0,
        damping=18.0,
    ).start()
    sliced = SpringAnimation(
        0.0,
        100.0,
        sliced_values.append,
        stiffness=180.0,
        damping=18.0,
    ).start()

    direct.advance(0.45)
    for _ in range(9):
        sliced.advance(0.05)

    assert direct.position == pytest.approx(sliced.position, rel=1e-12, abs=1e-12)
    assert direct.velocity == pytest.approx(sliced.velocity, rel=1e-12, abs=1e-12)
    assert direct_values[-1] == pytest.approx(sliced_values[-1], rel=1e-12, abs=1e-12)


def test_spring_supports_under_critical_and_over_damped_motion() -> None:
    for damping in (8.0, 20.0, 40.0):
        values: list[float] = []
        completed: list[str] = []
        spring = SpringAnimation(
            10.0,
            -5.0,
            values.append,
            mass=1.0,
            stiffness=100.0,
            damping=damping,
            max_duration=5.0,
            position_threshold=0.001,
            velocity_threshold=0.001,
            on_complete=lambda: completed.append("done"),
        ).start()

        for _ in range(600):
            if spring.status is AnimationStatus.COMPLETED:
                break
            spring.advance(1.0 / 120.0)

        assert spring.status is AnimationStatus.COMPLETED
        assert spring.position == -5.0
        assert spring.velocity == 0.0
        assert values[-1] == -5.0
        assert completed == ["done"]


def test_spring_cancel_preserves_current_sample() -> None:
    values: list[float] = []
    spring = SpringAnimation(0.0, 1.0, values.append).start()
    spring.advance(0.1)
    sampled = values[-1]

    assert spring.cancel() is True
    assert spring.cancel() is False
    assert spring.advance(1.0) == 1.0
    assert values[-1] == sampled
    assert spring.status is AnimationStatus.CANCELLED


def test_spring_rejects_invalid_physical_parameters() -> None:
    with pytest.raises(ValueError, match="mass"):
        SpringAnimation(0.0, 1.0, lambda _value: None, mass=0.0)
    with pytest.raises(ValueError, match="stiffness"):
        SpringAnimation(0.0, 1.0, lambda _value: None, stiffness=-1.0)
    with pytest.raises(ValueError, match="damping"):
        SpringAnimation(0.0, 1.0, lambda _value: None, damping=-1.0)
    with pytest.raises(ValueError, match="position_threshold"):
        SpringAnimation(0.0, 1.0, lambda _value: None, position_threshold=0.0)
    with pytest.raises(ValueError, match="max_duration"):
        SpringAnimation(0.0, 1.0, lambda _value: None, max_duration=math.inf)


def test_decay_sampling_is_independent_of_frame_partition_and_returns_tail() -> None:
    direct_values: list[float] = []
    sliced_values: list[float] = []
    direct = DecayAnimation(
        10.0,
        120.0,
        direct_values.append,
        friction=5.0,
        velocity_threshold=1.0,
    ).start()
    sliced = DecayAnimation(
        10.0,
        120.0,
        sliced_values.append,
        friction=5.0,
        velocity_threshold=1.0,
    ).start()

    direct.advance(0.4)
    for _ in range(8):
        sliced.advance(0.05)

    assert direct.position == pytest.approx(sliced.position, rel=1e-12, abs=1e-12)
    assert direct.velocity == pytest.approx(sliced.velocity, rel=1e-12, abs=1e-12)

    remaining = direct.duration - direct.elapsed
    unused = direct.advance(remaining + 0.25)
    expected_final = 10.0 + 120.0 * (1.0 - math.exp(-5.0 * direct.duration)) / 5.0

    assert unused == pytest.approx(0.25)
    assert direct.status is AnimationStatus.COMPLETED
    assert direct.position == pytest.approx(expected_final)
    assert direct.velocity == 0.0


def test_decay_handles_negative_velocity_and_validation() -> None:
    values: list[float] = []
    decay = DecayAnimation(50.0, -80.0, values.append, friction=4.0).start()
    decay.advance(0.2)

    assert decay.position < 50.0
    assert decay.velocity < 0.0

    with pytest.raises(ValueError, match="friction"):
        DecayAnimation(0.0, 1.0, lambda _value: None, friction=0.0)
    with pytest.raises(ValueError, match="velocity_threshold"):
        DecayAnimation(0.0, 1.0, lambda _value: None, velocity_threshold=-1.0)


def test_parallel_group_uses_same_clock_and_returns_slowest_tail() -> None:
    fast_values: list[float] = []
    slow_values: list[float] = []
    completed: list[str] = []
    group = AnimationParallel(
        Tween(0.0, 1.0, 0.25, fast_values.append),
        Tween(10.0, 20.0, 0.5, slow_values.append),
        on_complete=lambda: completed.append("parallel"),
    ).start()

    unused = group.advance(0.75)
    group.advance(1.0)

    assert unused == pytest.approx(0.25)
    assert fast_values[-1] == 1.0
    assert slow_values[-1] == 20.0
    assert group.status is AnimationStatus.COMPLETED
    assert completed == ["parallel"]


def test_parallel_group_cancellation_cascades_to_unfinished_children() -> None:
    first = Tween(0.0, 1.0, 1.0, lambda _value: None)
    second = SpringAnimation(0.0, 1.0, lambda _value: None)
    group = AnimationParallel(first, second).start()
    group.advance(0.1)

    assert group.cancel() is True
    assert group.cancel() is False
    assert group.status is AnimationStatus.CANCELLED
    assert first.status is AnimationStatus.CANCELLED
    assert second.status is AnimationStatus.CANCELLED


def test_sequence_can_chain_parallel_and_physics_animations() -> None:
    x_values: list[float] = []
    opacity_values: list[float] = []
    tail_values: list[float] = []
    group = AnimationParallel(
        Tween(0.0, 1.0, 0.1, opacity_values.append),
        DecayAnimation(0.0, 20.0, x_values.append, friction=10.0, velocity_threshold=10.0),
    )
    sequence = AnimationSequence(group, Tween(0.0, 5.0, 0.1, tail_values.append)).start()

    sequence.advance(1.0)

    assert sequence.status is AnimationStatus.COMPLETED
    assert opacity_values[-1] == 1.0
    assert x_values[-1] == pytest.approx(group.animations[1].final_position)  # type: ignore[attr-defined]
    assert tail_values[-1] == 5.0


def test_spring_and_decay_state_helpers_publish_reactive_samples() -> None:
    spring_value = State(0.0)
    decay_value = State(10.0)
    spring = spring_state(
        spring_value,
        5.0,
        stiffness=120.0,
        damping=30.0,
        max_duration=2.0,
    ).start()
    decay = decay_state(
        decay_value,
        30.0,
        friction=8.0,
        velocity_threshold=5.0,
    ).start()

    spring.advance(0.2)
    decay.advance(0.2)

    assert spring_value.value == pytest.approx(spring.position)
    assert decay_value.value == pytest.approx(decay.position)
    assert spring_value.value > 0.0
    assert decay_value.value > 10.0


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

    # FrameScheduler has no delta on its first rendered frame. The controller
    # must keep the window invalidated so the second frame can begin timing.
    app.emit("frame_rendered", window=first_window, frame_delta=None)
    assert values[-1] == 0.0
    assert controller.active_count == 1

    app.emit("frame_rendered", window=first_window, frame_delta=0.25)
    assert values[-1] == pytest.approx(2.5)
    assert controller.active_count == 1

    controller.dispose()
    app.emit("frame_rendered", window=first_window, frame_delta=0.25)
    assert values[-1] == pytest.approx(2.5)
    assert tween.status is AnimationStatus.CANCELLED
    assert controller.active_count == 0


def test_controller_drives_physics_and_parallel_animations() -> None:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(title="Physics"))
    spring_values: list[float] = []
    decay_values: list[float] = []
    group = AnimationParallel(
        SpringAnimation(0.0, 10.0, spring_values.append, damping=30.0, max_duration=1.0),
        DecayAnimation(0.0, 20.0, decay_values.append, friction=8.0, velocity_threshold=5.0),
    )
    controller = AnimationController(app, window)

    controller.play(group)
    app.emit("frame_rendered", window=window, frame_delta=0.1)

    assert spring_values[-1] > 0.0
    assert decay_values[-1] > 0.0
    assert controller.active_count == 1

    controller.dispose()
    assert group.status is AnimationStatus.CANCELLED


def test_controller_rejects_play_after_dispose() -> None:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window())
    controller = AnimationController(app, window)
    controller.dispose()

    with pytest.raises(RuntimeError, match="disposed"):
        controller.play(Tween(0.0, 1.0, 1.0, lambda _value: None))
