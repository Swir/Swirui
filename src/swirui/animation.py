"""Frame-rate-independent animation primitives for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING, TypeAlias

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

    def then(self, *animations: Tween) -> AnimationSequence:
        """Build a sequence beginning with this tween."""

        return AnimationSequence(self, *animations)

    def _finish(self) -> None:
        self._elapsed = self.duration
        self.update(self.to_value)
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class AnimationSequence:
    """Play tweens serially with deterministic cross-frame carry-over."""

    def __init__(self, *animations: Tween, on_complete: Callable[[], None] | None = None) -> None:
        if not animations:
            raise ValueError("AnimationSequence requires at least one tween.")
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
        """Start or restart the sequence from its first tween."""

        self._index = 0
        self._status = AnimationStatus.RUNNING
        self.animations[0].start()
        self._skip_completed_zero_duration_tweens()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance the active tween and carry leftover time into later tweens."""

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
        """Cancel the active tween and the sequence as one operation."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        if self._status is AnimationStatus.RUNNING:
            self.animations[self._index].cancel()
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: Tween) -> AnimationSequence:
        """Return a new sequence with additional tweens appended."""

        return AnimationSequence(*self.animations, *animations, on_complete=self.on_complete)

    def _advance_to_next(self) -> bool:
        self._index += 1
        if self._index >= len(self.animations):
            self._complete()
            return False
        self.animations[self._index].start()
        self._skip_completed_zero_duration_tweens()
        return self._status is AnimationStatus.RUNNING

    def _skip_completed_zero_duration_tweens(self) -> None:
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


Animation: TypeAlias = Tween | AnimationSequence


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
        self._animations: list[Animation] = []
        self._unsubscribe = app.on("frame_rendered", self._on_frame_rendered)
        self._disposed = False

    @property
    def active_count(self) -> int:
        return len(self._animations)

    def play(self, animation: Animation) -> Animation:
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


def _finite_float(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized
