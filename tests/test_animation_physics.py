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
    spring_state,
)
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


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


@pytest.mark.parametrize("damping", [8.0, 20.0, 40.0])
def test_spring_supports_all_damping_regimes(damping: float) -> None:
    values: list[float] = []
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
    ).start()

    for _ in range(600):
        if spring.status is AnimationStatus.COMPLETED:
            break
        spring.advance(1.0 / 120.0)

    assert spring.status is AnimationStatus.COMPLETED
    assert spring.position == -5.0
    assert spring.velocity == 0.0
    assert values[-1] == -5.0


def test_spring_completion_callback_fires_once_and_cancel_preserves_sample() -> None:
    completed: list[str] = []
    values: list[float] = []
    spring = SpringAnimation(
        0.0,
        1.0,
        values.append,
        max_duration=0.1,
        on_complete=lambda: completed.append("done"),
    ).start()

    unused = spring.advance(0.3)
    spring.advance(1.0)

    assert unused == pytest.approx(0.2)
    assert spring.status is AnimationStatus.COMPLETED
    assert values[-1] == 1.0
    assert completed == ["done"]

    cancelled_values: list[float] = []
    cancelled = SpringAnimation(0.0, 1.0, cancelled_values.append).start()
    cancelled.advance(0.1)
    sampled = cancelled_values[-1]
    assert cancelled.cancel() is True
    assert cancelled.cancel() is False
    assert cancelled.advance(1.0) == 1.0
    assert cancelled_values[-1] == sampled


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
    decay = DecayAnimation(0.0, 20.0, x_values.append, friction=10.0, velocity_threshold=10.0)
    group = AnimationParallel(Tween(0.0, 1.0, 0.1, opacity_values.append), decay)
    sequence = AnimationSequence(group, Tween(0.0, 5.0, 0.1, tail_values.append)).start()

    sequence.advance(1.0)

    assert sequence.status is AnimationStatus.COMPLETED
    assert opacity_values[-1] == 1.0
    assert x_values[-1] == pytest.approx(decay.final_position)
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


def test_animation_controller_drives_physics_and_parallel_animations() -> None:
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
