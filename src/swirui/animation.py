"""Frame-rate-independent animation primitives for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypeAlias

from .core import Event, State

if TYPE_CHECKING:
    from .app import App
    from .window import Window

Easing = Callable[[float], float]


class AnimationStatus(StrEnum):
    """Lifecycle state shared by SwirUI animation primitives."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AnimationPlayable(Protocol):
    """Structural contract consumed by animation groups and controllers."""

    @property
    def status(self) -> AnimationStatus: ...

    def start(self) -> AnimationPlayable: ...

    def advance(self, delta_seconds: float) -> float: ...

    def cancel(self) -> bool: ...


Animation: TypeAlias = AnimationPlayable


def linear(progress: float) -> float:
    """Return unchanged normalized animation progress."""

    return progress


def ease_in_out_cubic(progress: float) -> float:
    """Smooth cubic easing with zero slope near both endpoints."""

    if progress < 0.5:
        return 4.0 * progress * progress * progress
    return 1.0 - ((-2.0 * progress + 2.0) ** 3) / 2.0


def ease_out_cubic(progress: float) -> float:
    """Cubic deceleration toward the target value."""

    return 1.0 - (1.0 - progress) ** 3


def ease_out_bounce(progress: float) -> float:
    """Deterministic piecewise bounce easing for value tweens."""

    n1 = 7.5625
    d1 = 2.75
    if progress < 1.0 / d1:
        return n1 * progress * progress
    if progress < 2.0 / d1:
        shifted = progress - 1.5 / d1
        return n1 * shifted * shifted + 0.75
    if progress < 2.5 / d1:
        shifted = progress - 2.25 / d1
        return n1 * shifted * shifted + 0.9375
    shifted = progress - 2.625 / d1
    return n1 * shifted * shifted + 0.984375


def ease_out_elastic(progress: float) -> float:
    """Deterministic overshooting elastic easing for value tweens."""

    if progress == 0.0 or progress == 1.0:
        return progress
    period = (2.0 * math.pi) / 3.0
    return math.pow(2.0, -10.0 * progress) * math.sin((progress * 10.0 - 0.75) * period) + 1.0


class Tween:
    """Animate one numeric value using elapsed time rather than frame count.

    ``advance()`` consumes seconds and returns any unused tail when the tween
    completes. That carry-over contract lets :class:`AnimationSequence` stay
    deterministic even when one frame crosses an animation boundary.
    """

    def __init__(
        self,
        from_value: float,
        to_value: float,
        duration: float,
        update: Callable[[float], None],
        *,
        easing: Easing = linear,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.from_value = _finite_float("from_value", from_value)
        self.to_value = _finite_float("to_value", to_value)
        self.duration = _finite_float("duration", duration)
        if self.duration < 0.0:
            raise ValueError("duration must be non-negative.")
        self.update = update
        self.easing = easing
        self.on_complete = on_complete
        self._elapsed = 0.0
        self._status = AnimationStatus.IDLE

    @property
    def status(self) -> AnimationStatus:
        return self._status

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def progress(self) -> float:
        if self.duration == 0.0:
            return 1.0 if self._status is AnimationStatus.COMPLETED else 0.0
        return min(1.0, self._elapsed / self.duration)

    def start(self) -> Tween:
        """Start or restart this tween from its authored source value."""

        self._elapsed = 0.0
        self._status = AnimationStatus.RUNNING
        self.update(self.from_value)
        if self.duration == 0.0:
            self._finish()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance by elapsed seconds and return any unconsumed positive tail."""

        delta = _finite_float("delta_seconds", delta_seconds)
        if delta < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return delta

        remaining_duration = max(0.0, self.duration - self._elapsed)
        consumed = min(delta, remaining_duration)
        self._elapsed += consumed

        if self._elapsed >= self.duration:
            self._finish()
            return max(0.0, delta - consumed)

        normalized = self._elapsed / self.duration
        eased = _finite_float("easing result", self.easing(normalized))
        value = self.from_value + (self.to_value - self.from_value) * eased
        self.update(value)
        return max(0.0, delta - consumed)

    def cancel(self) -> bool:
        """Cancel without forcing the target value or firing completion."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a sequence beginning with this animation."""

        return AnimationSequence(self, *animations)

    def _finish(self) -> None:
        self._elapsed = self.duration
        self.update(self.to_value)
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class SpringAnimation:
    """Analytical damped-spring animation with frame-partition-independent sampling.

    The spring solves the second-order mass/stiffness/damping system directly at
    absolute elapsed time instead of numerically integrating frame deltas. Values
    sampled at the same elapsed time therefore match at 60, 120, 144 Hz or under
    irregular frame pacing. The animation settles when both displacement and
    velocity are within explicit tolerances, with ``max_duration`` as a hard bound.
    """

    def __init__(
        self,
        from_value: float,
        to_value: float,
        update: Callable[[float], None],
        *,
        mass: float = 1.0,
        stiffness: float = 170.0,
        damping: float = 26.0,
        initial_velocity: float = 0.0,
        position_threshold: float = 0.001,
        velocity_threshold: float = 0.001,
        max_duration: float = 10.0,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.from_value = _finite_float("from_value", from_value)
        self.to_value = _finite_float("to_value", to_value)
        self.update = update
        self.mass = _positive_float("mass", mass)
        self.stiffness = _positive_float("stiffness", stiffness)
        self.damping = _non_negative_float("damping", damping)
        self.initial_velocity = _finite_float("initial_velocity", initial_velocity)
        self.position_threshold = _positive_float("position_threshold", position_threshold)
        self.velocity_threshold = _positive_float("velocity_threshold", velocity_threshold)
        self.max_duration = _positive_float("max_duration", max_duration)
        self.on_complete = on_complete
        self._elapsed = 0.0
        self._position = self.from_value
        self._velocity = self.initial_velocity
        self._status = AnimationStatus.IDLE

    @property
    def status(self) -> AnimationStatus:
        return self._status

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def position(self) -> float:
        return self._position

    @property
    def velocity(self) -> float:
        return self._velocity

    @property
    def progress(self) -> float:
        if self._status is AnimationStatus.COMPLETED:
            return 1.0
        return min(1.0, self._elapsed / self.max_duration)

    def start(self) -> SpringAnimation:
        """Start or restart from the authored position and initial velocity."""

        self._elapsed = 0.0
        self._position = self.from_value
        self._velocity = self.initial_velocity
        self._status = AnimationStatus.RUNNING
        self.update(self._position)
        if self._is_settled():
            self._finish()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance the analytical spring and return any hard-bound frame tail."""

        delta = _finite_float("delta_seconds", delta_seconds)
        if delta < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return delta

        remaining_duration = max(0.0, self.max_duration - self._elapsed)
        consumed = min(delta, remaining_duration)
        self._elapsed += consumed
        self._position, self._velocity = self._sample(self._elapsed)
        self.update(self._position)

        if self._is_settled() or self._elapsed >= self.max_duration:
            self._finish()
            return max(0.0, delta - consumed)
        return max(0.0, delta - consumed)

    def cancel(self) -> bool:
        """Cancel without snapping to the target or firing completion."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a serial sequence beginning with this spring."""

        return AnimationSequence(self, *animations)

    def _sample(self, elapsed: float) -> tuple[float, float]:
        displacement = self.from_value - self.to_value
        omega = math.sqrt(self.stiffness / self.mass)
        damping_ratio = self.damping / (2.0 * math.sqrt(self.stiffness * self.mass))

        if damping_ratio < 1.0 - 1e-9:
            damped_omega = omega * math.sqrt(1.0 - damping_ratio * damping_ratio)
            a = displacement
            b = (self.initial_velocity + damping_ratio * omega * displacement) / damped_omega
            envelope = math.exp(-damping_ratio * omega * elapsed)
            cos_term = math.cos(damped_omega * elapsed)
            sin_term = math.sin(damped_omega * elapsed)
            local = a * cos_term + b * sin_term
            local_velocity = (
                -damping_ratio * omega * local
                + (-a * damped_omega * sin_term + b * damped_omega * cos_term)
            )
            return self.to_value + envelope * local, envelope * local_velocity

        if damping_ratio <= 1.0 + 1e-9:
            a = displacement
            b = self.initial_velocity + omega * displacement
            envelope = math.exp(-omega * elapsed)
            local = a + b * elapsed
            local_velocity = b - omega * local
            return self.to_value + envelope * local, envelope * local_velocity

        root = math.sqrt(damping_ratio * damping_ratio - 1.0)
        r1 = -omega * (damping_ratio - root)
        r2 = -omega * (damping_ratio + root)
        c1 = (self.initial_velocity - r2 * displacement) / (r1 - r2)
        c2 = displacement - c1
        exp1 = math.exp(r1 * elapsed)
        exp2 = math.exp(r2 * elapsed)
        local = c1 * exp1 + c2 * exp2
        local_velocity = c1 * r1 * exp1 + c2 * r2 * exp2
        return self.to_value + local, local_velocity

    def _is_settled(self) -> bool:
        return (
            abs(self._position - self.to_value) <= self.position_threshold
            and abs(self._velocity) <= self.velocity_threshold
        )

    def _finish(self) -> None:
        self._position = self.to_value
        self._velocity = 0.0
        self.update(self.to_value)
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class DecayAnimation:
    """Analytical inertial decay useful for fling, momentum and kinetic motion."""

    def __init__(
        self,
        from_value: float,
        initial_velocity: float,
        update: Callable[[float], None],
        *,
        friction: float = 6.0,
        velocity_threshold: float = 1.0,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.from_value = _finite_float("from_value", from_value)
        self.initial_velocity = _finite_float("initial_velocity", initial_velocity)
        self.update = update
        self.friction = _positive_float("friction", friction)
        self.velocity_threshold = _positive_float("velocity_threshold", velocity_threshold)
        self.on_complete = on_complete
        speed = abs(self.initial_velocity)
        self.duration = (
            0.0
            if speed <= self.velocity_threshold
            else math.log(speed / self.velocity_threshold) / self.friction
        )
        self._elapsed = 0.0
        self._position = self.from_value
        self._velocity = self.initial_velocity
        self._status = AnimationStatus.IDLE

    @property
    def status(self) -> AnimationStatus:
        return self._status

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def position(self) -> float:
        return self._position

    @property
    def velocity(self) -> float:
        return self._velocity

    @property
    def progress(self) -> float:
        if self.duration == 0.0:
            return 1.0 if self._status is AnimationStatus.COMPLETED else 0.0
        return min(1.0, self._elapsed / self.duration)

    @property
    def final_position(self) -> float:
        return self._sample_position(self.duration)

    def start(self) -> DecayAnimation:
        """Start or restart the decay from its authored position and velocity."""

        self._elapsed = 0.0
        self._position = self.from_value
        self._velocity = self.initial_velocity
        self._status = AnimationStatus.RUNNING
        self.update(self._position)
        if self.duration == 0.0:
            self._finish()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance the closed-form decay and return unused tail after completion."""

        delta = _finite_float("delta_seconds", delta_seconds)
        if delta < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return delta

        remaining_duration = max(0.0, self.duration - self._elapsed)
        consumed = min(delta, remaining_duration)
        self._elapsed += consumed
        self._position = self._sample_position(self._elapsed)
        self._velocity = self.initial_velocity * math.exp(-self.friction * self._elapsed)
        self.update(self._position)

        if self._elapsed >= self.duration:
            self._finish()
        return max(0.0, delta - consumed)

    def cancel(self) -> bool:
        """Cancel without changing the current sample or firing completion."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a serial sequence beginning with this inertial decay."""

        return AnimationSequence(self, *animations)

    def _sample_position(self, elapsed: float) -> float:
        displacement = (
            self.initial_velocity * (1.0 - math.exp(-self.friction * elapsed)) / self.friction
        )
        return self.from_value + displacement

    def _finish(self) -> None:
        self._elapsed = self.duration
        self._position = self.final_position
        self._velocity = 0.0
        self.update(self._position)
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class AnimationSequence:
    """Play animations serially with deterministic cross-frame carry-over."""

    def __init__(
        self,
        *animations: AnimationPlayable,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if not animations:
            raise ValueError("AnimationSequence requires at least one animation.")
        self.animations = tuple(animations)
        self.on_complete = on_complete
        self._index = 0
        self._status = AnimationStatus.IDLE

    @property
    def status(self) -> AnimationStatus:
        return self._status

    @property
    def current_index(self) -> int:
        return self._index

    def start(self) -> AnimationSequence:
        """Start or restart the sequence from its first animation."""

        self._index = 0
        self._status = AnimationStatus.RUNNING
        self.animations[0].start()
        self._skip_completed_zero_duration_animations()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance the active animation and carry leftover time into later work."""

        remaining = _finite_float("delta_seconds", delta_seconds)
        if remaining < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return remaining

        while self._status is AnimationStatus.RUNNING:
            current = self.animations[self._index]
            if current.status is AnimationStatus.CANCELLED:
                self._status = AnimationStatus.CANCELLED
                return remaining
            remaining = current.advance(remaining)
            if current.status is not AnimationStatus.COMPLETED:
                break
            if not self._advance_to_next():
                return remaining
            if remaining <= 0.0:
                break
        return remaining

    def cancel(self) -> bool:
        """Cancel the active animation and the sequence as one operation."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        if self._status is AnimationStatus.RUNNING:
            self.animations[self._index].cancel()
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Return a new sequence with additional animations appended."""

        return AnimationSequence(*self.animations, *animations, on_complete=self.on_complete)

    def _advance_to_next(self) -> bool:
        self._index += 1
        if self._index >= len(self.animations):
            self._complete()
            return False
        self.animations[self._index].start()
        self._skip_completed_zero_duration_animations()
        return self._status is AnimationStatus.RUNNING

    def _skip_completed_zero_duration_animations(self) -> None:
        while (
            self._status is AnimationStatus.RUNNING
            and self.animations[self._index].status is AnimationStatus.COMPLETED
        ):
            if not self._advance_to_next():
                break

    def _complete(self) -> None:
        self._index = len(self.animations) - 1
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class AnimationParallel:
    """Advance multiple animations against the same frame clock."""

    def __init__(
        self,
        *animations: AnimationPlayable,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if not animations:
            raise ValueError("AnimationParallel requires at least one animation.")
        self.animations = tuple(animations)
        self.on_complete = on_complete
        self._status = AnimationStatus.IDLE

    @property
    def status(self) -> AnimationStatus:
        return self._status

    def start(self) -> AnimationParallel:
        """Start or restart all child animations together."""

        self._status = AnimationStatus.RUNNING
        for animation in self.animations:
            animation.start()
        if all(animation.status is AnimationStatus.COMPLETED for animation in self.animations):
            self._complete()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance every active child using the same elapsed frame delta."""

        delta = _finite_float("delta_seconds", delta_seconds)
        if delta < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return delta

        if any(animation.status is AnimationStatus.CANCELLED for animation in self.animations):
            self.cancel()
            return delta

        leftovers = [animation.advance(delta) for animation in self.animations]
        if any(animation.status is AnimationStatus.CANCELLED for animation in self.animations):
            self.cancel()
            return 0.0
        if all(animation.status is AnimationStatus.COMPLETED for animation in self.animations):
            self._complete()
            return min(leftovers)
        return 0.0

    def cancel(self) -> bool:
        """Cancel every unfinished child animation."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        for animation in self.animations:
            if animation.status is not AnimationStatus.COMPLETED:
                animation.cancel()
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a serial sequence beginning with this parallel group."""

        return AnimationSequence(self, *animations)

    def _complete(self) -> None:
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class AnimationController:
    """Drive animations from one window's real rendered frame cadence.

    The controller listens to ``App.frame_rendered`` telemetry and advances only
    for its own window, preventing multi-window applications from double-stepping
    an animation. While work remains it invalidates that window so the existing
    display-aware scheduler supplies the next frame.
    """

    def __init__(self, app: App, window: Window) -> None:
        self.app = app
        self.window = window
        self._animations: list[AnimationPlayable] = []
        self._unsubscribe = app.on("frame_rendered", self._on_frame_rendered)
        self._disposed = False

    @property
    def active_count(self) -> int:
        return len(self._animations)

    def play(self, animation: AnimationPlayable) -> AnimationPlayable:
        """Start one animation and schedule its first presentation frame."""

        if self._disposed:
            raise RuntimeError("AnimationController is disposed.")
        animation.start()
        if animation.status is AnimationStatus.RUNNING and animation not in self._animations:
            self._animations.append(animation)
        self.app.invalidate(self.window)
        return animation

    def tick(self, delta_seconds: float) -> int:
        """Advance all active animations once and return the remaining count."""

        delta = _finite_float("delta_seconds", delta_seconds)
        if delta < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if not self._animations:
            return 0

        for animation in tuple(self._animations):
            animation.advance(delta)
        self._animations = [
            animation
            for animation in self._animations
            if animation.status is AnimationStatus.RUNNING
        ]
        self.app.invalidate(self.window)
        return len(self._animations)

    def cancel_all(self) -> int:
        """Cancel every active animation and return how many were cancelled."""

        cancelled = 0
        for animation in tuple(self._animations):
            cancelled += int(animation.cancel())
        self._animations.clear()
        return cancelled

    def dispose(self, *, cancel: bool = True) -> None:
        """Detach from the application frame stream."""

        if self._disposed:
            return
        if cancel:
            self.cancel_all()
        self._unsubscribe()
        self._disposed = True

    def _on_frame_rendered(self, event: Event) -> None:
        if event.data.get("window") is not self.window:
            return
        frame_delta = event.data.get("frame_delta")
        if frame_delta is None:
            if self._animations:
                self.app.invalidate(self.window)
            return
        if not isinstance(frame_delta, (int, float)):
            return
        delta = float(frame_delta)
        if not math.isfinite(delta) or delta < 0.0:
            return
        self.tick(delta)


def tween_state(
    state: State[float],
    to_value: float,
    duration: float,
    *,
    easing: Easing = linear,
    on_complete: Callable[[], None] | None = None,
) -> Tween:
    """Create a tween that writes each sampled value into a reactive State."""

    def update(value: float) -> None:
        state.set(value)

    return Tween(
        float(state.value),
        to_value,
        duration,
        update,
        easing=easing,
        on_complete=on_complete,
    )


def spring_state(
    state: State[float],
    to_value: float,
    *,
    mass: float = 1.0,
    stiffness: float = 170.0,
    damping: float = 26.0,
    initial_velocity: float = 0.0,
    position_threshold: float = 0.001,
    velocity_threshold: float = 0.001,
    max_duration: float = 10.0,
    on_complete: Callable[[], None] | None = None,
) -> SpringAnimation:
    """Create an analytical spring that writes samples into reactive State."""

    def update(value: float) -> None:
        state.set(value)

    return SpringAnimation(
        float(state.value),
        to_value,
        update,
        mass=mass,
        stiffness=stiffness,
        damping=damping,
        initial_velocity=initial_velocity,
        position_threshold=position_threshold,
        velocity_threshold=velocity_threshold,
        max_duration=max_duration,
        on_complete=on_complete,
    )


def decay_state(
    state: State[float],
    initial_velocity: float,
    *,
    friction: float = 6.0,
    velocity_threshold: float = 1.0,
    on_complete: Callable[[], None] | None = None,
) -> DecayAnimation:
    """Create an inertial decay that writes samples into reactive State."""

    def update(value: float) -> None:
        state.set(value)

    return DecayAnimation(
        float(state.value),
        initial_velocity,
        update,
        friction=friction,
        velocity_threshold=velocity_threshold,
        on_complete=on_complete,
    )


def _finite_float(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


def _positive_float(name: str, value: float) -> float:
    normalized = _finite_float(name, value)
    if normalized <= 0.0:
        raise ValueError(f"{name} must be positive.")
    return normalized


def _non_negative_float(name: str, value: float) -> float:
    normalized = _finite_float(name, value)
    if normalized < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return normalized
