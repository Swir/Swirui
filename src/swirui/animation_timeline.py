"""Deterministic timeline helpers for composing SwirUI animations."""

from __future__ import annotations

import math
from collections.abc import Callable

from .animation import AnimationPlayable, AnimationSequence, AnimationStatus


class DelayAnimation:
    """Consume elapsed time without mutating visual state.

    Delays use the same unused-frame-tail contract as SwirUI tweens so a frame
    that crosses the delay boundary can continue immediately into the next item
    in an :class:`~swirui.animation.AnimationSequence`.
    """

    def __init__(
        self,
        duration: float,
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.duration = _non_negative_finite("duration", duration)
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

    def start(self) -> DelayAnimation:
        """Start or restart the delay from zero elapsed time."""

        self._elapsed = 0.0
        self._status = AnimationStatus.RUNNING
        if self.duration == 0.0:
            self._finish()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance the delay and return any unused positive frame tail."""

        delta = _non_negative_finite("delta_seconds", delta_seconds)
        if self._status is not AnimationStatus.RUNNING:
            return delta

        remaining_duration = max(0.0, self.duration - self._elapsed)
        consumed = min(delta, remaining_duration)
        self._elapsed += consumed
        if self._elapsed >= self.duration:
            self._finish()
        return max(0.0, delta - consumed)

    def cancel(self) -> bool:
        """Cancel without forcing completion or firing ``on_complete``."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a serial sequence beginning with this delay."""

        return AnimationSequence(self, *animations)

    def _finish(self) -> None:
        self._elapsed = self.duration
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


class RepeatAnimation:
    """Repeat one restartable animation a finite number of times.

    Built-in SwirUI animations define ``start()`` as a deterministic restart.
    ``RepeatAnimation`` builds on that contract while preserving unused frame
    time across iteration boundaries. The repeat count is deliberately finite so
    zero-duration children cannot create an unbounded loop inside one frame.
    """

    def __init__(
        self,
        animation: AnimationPlayable,
        count: int,
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer.")
        self.animation = animation
        self.count = count
        self.on_complete = on_complete
        self._completed_iterations = 0
        self._status = AnimationStatus.IDLE

    @property
    def status(self) -> AnimationStatus:
        return self._status

    @property
    def completed_iterations(self) -> int:
        return self._completed_iterations

    def start(self) -> RepeatAnimation:
        """Restart the repeated timeline from its first iteration."""

        self._completed_iterations = 0
        self._status = AnimationStatus.RUNNING
        self.animation.start()
        self._consume_immediate_completions()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance iterations and carry unused time across repeat boundaries."""

        remaining = _non_negative_finite("delta_seconds", delta_seconds)
        if self._status is not AnimationStatus.RUNNING:
            return remaining

        while self._status is AnimationStatus.RUNNING:
            status_before = self.animation.status
            if status_before is AnimationStatus.CANCELLED:
                self._status = AnimationStatus.CANCELLED
                return remaining
            if status_before is AnimationStatus.IDLE:
                raise RuntimeError("Repeated animation returned to IDLE while running.")

            before = remaining
            remaining = _valid_tail(self.animation.advance(remaining), before)
            status_after = self.animation.status
            if status_after is AnimationStatus.CANCELLED:
                self._status = AnimationStatus.CANCELLED
                return remaining
            if status_after is AnimationStatus.RUNNING:
                return remaining
            if status_after is not AnimationStatus.COMPLETED:
                raise RuntimeError("Repeated animation entered an unsupported status.")

            self._completed_iterations += 1
            if self._completed_iterations >= self.count:
                self._finish()
                return remaining

            self.animation.start()
            self._consume_immediate_completions()
            if self._status is not AnimationStatus.RUNNING or remaining <= 0.0:
                return remaining
            restarted_status = self.animation.status
            if restarted_status is AnimationStatus.RUNNING and remaining == before:
                return remaining

        return remaining

    def cancel(self) -> bool:
        """Cancel the active child and the repeat wrapper as one operation."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        if self._status is AnimationStatus.RUNNING:
            self.animation.cancel()
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a serial sequence beginning with this repeat wrapper."""

        return AnimationSequence(self, *animations)

    def _consume_immediate_completions(self) -> None:
        while (
            self._status is AnimationStatus.RUNNING
            and self.animation.status is AnimationStatus.COMPLETED
        ):
            self._completed_iterations += 1
            if self._completed_iterations >= self.count:
                self._finish()
                return
            self.animation.start()

        if (
            self._status is AnimationStatus.RUNNING
            and self.animation.status is AnimationStatus.CANCELLED
        ):
            self._status = AnimationStatus.CANCELLED
        elif (
            self._status is AnimationStatus.RUNNING
            and self.animation.status is AnimationStatus.IDLE
        ):
            raise RuntimeError(
                "Repeated animation did not enter RUNNING or COMPLETED on start()."
            )

    def _finish(self) -> None:
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()


def _non_negative_finite(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized


def _valid_tail(value: float, input_delta: float) -> float:
    tail = float(value)
    if not math.isfinite(tail) or tail < 0.0 or tail > input_delta:
        raise RuntimeError("Animation returned an invalid unused frame tail.")
    return tail
