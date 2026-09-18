"""Frame-rate-independent animation primitives for SwirUI.

The animation layer is renderer-agnostic. It advances from absolute monotonic time rather
than frame counts, so dropped or high-refresh frames do not change animation duration.
Widget helpers mutate existing retained properties; their ordinary invalidation path keeps
SceneGraph and native GPU presentation synchronized.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypeAlias

from .core.events import Event
from .rendering.geometry import Rect

if TYPE_CHECKING:
    from .app import App

EasingFunction: TypeAlias = Callable[[float], float]
ValueUpdate: TypeAlias = Callable[[float], None]


def _clamp_unit(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def linear(progress: float) -> float:
    """Return clamped linear animation progress."""

    return _clamp_unit(progress)


def ease_in_cubic(progress: float) -> float:
    """Cubic acceleration easing."""

    value = _clamp_unit(progress)
    return value * value * value


def ease_out_cubic(progress: float) -> float:
    """Cubic deceleration easing."""

    value = 1.0 - _clamp_unit(progress)
    return 1.0 - value * value * value


def ease_in_out_cubic(progress: float) -> float:
    """Symmetric cubic acceleration/deceleration easing."""

    value = _clamp_unit(progress)
    if value < 0.5:
        return 4.0 * value * value * value
    tail = -2.0 * value + 2.0
    return 1.0 - (tail * tail * tail) / 2.0


class AnimationStatus(StrEnum):
    """Lifecycle state of a running animation sequence."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Tween:
    """One scalar animation segment.

    ``duration`` and ``delay`` are expressed in seconds. The update callback receives the
    interpolated scalar value. A sequence may combine unrelated callbacks, which makes one
    timeline useful for opacity, geometry, state or application-defined values.
    """

    start: float
    end: float
    duration: float
    update: ValueUpdate
    easing: EasingFunction = linear
    delay: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.start) or not math.isfinite(self.end):
            raise ValueError("Tween endpoints must be finite numbers.")
        if not math.isfinite(self.duration) or self.duration <= 0.0:
            raise ValueError("Tween duration must be a finite positive number.")
        if not math.isfinite(self.delay) or self.delay < 0.0:
            raise ValueError("Tween delay must be a finite non-negative number.")

    def value_at(self, progress: float) -> float:
        """Return the eased value at normalized ``progress``."""

        normalized = _clamp_unit(progress)
        eased = float(self.easing(normalized))
        if not math.isfinite(eased):
            raise ValueError("Animation easing must return a finite number.")
        eased = _clamp_unit(eased)
        return self.start + (self.end - self.start) * eased

    def then(self, *next_tweens: Tween) -> AnimationSequence:
        """Create an immutable sequence beginning with this tween."""

        return AnimationSequence((self, *next_tweens))


@dataclass(frozen=True, slots=True)
class AnimationSequence:
    """Immutable ordered animation specification."""

    tweens: tuple[Tween, ...]

    def __post_init__(self) -> None:
        if not self.tweens:
            raise ValueError("AnimationSequence requires at least one Tween.")

    def then(self, *next_tweens: Tween) -> AnimationSequence:
        """Return a new sequence with additional animation segments appended."""

        if not next_tweens:
            return self
        return AnimationSequence((*self.tweens, *next_tweens))

    @classmethod
    def from_iterable(cls, tweens: Iterable[Tween]) -> AnimationSequence:
        """Build a sequence from an arbitrary iterable exactly once."""

        return cls(tuple(tweens))


class AnimationHandle:
    """Mutable runtime state for one animation sequence.

    The handle consumes absolute timestamps. Segment boundaries use their mathematically
    exact completion time, so a delayed frame can advance across multiple chained segments
    without stretching the total timeline.
    """

    def __init__(self, sequence: AnimationSequence) -> None:
        self.sequence = sequence
        self.status = AnimationStatus.IDLE
        self._index = 0
        self._segment_origin: float | None = None
        self._last_tick: float | None = None
        self._last_value: float | None = None

    @property
    def running(self) -> bool:
        return self.status is AnimationStatus.RUNNING

    @property
    def completed(self) -> bool:
        return self.status is AnimationStatus.COMPLETED

    @property
    def cancelled(self) -> bool:
        return self.status is AnimationStatus.CANCELLED

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def current_tween(self) -> Tween:
        return self.sequence.tweens[self._index]

    def start(self, at: float | None = None) -> AnimationHandle:
        """Start or restart this sequence at an absolute monotonic timestamp."""

        timestamp = time.monotonic() if at is None else float(at)
        if not math.isfinite(timestamp):
            raise ValueError("Animation start time must be finite.")
        self.status = AnimationStatus.RUNNING
        self._index = 0
        self._segment_origin = timestamp
        self._last_tick = timestamp
        self._last_value = None
        self._publish(self.current_tween.start)
        return self

    def tick(self, now: float | None = None) -> bool:
        """Advance the sequence and return whether a callback published a new value."""

        if not self.running:
            return False
        timestamp = time.monotonic() if now is None else float(now)
        if not math.isfinite(timestamp):
            raise ValueError("Animation tick time must be finite.")
        if self._last_tick is not None and timestamp < self._last_tick:
            raise ValueError("Animation timestamps must be monotonic.")
        self._last_tick = timestamp

        changed = False
        while self.running:
            tween = self.current_tween
            origin = self._segment_origin
            if origin is None:
                raise RuntimeError("Running animation has no segment origin.")
            active_start = origin + tween.delay
            if timestamp < active_start:
                return changed

            progress = (timestamp - active_start) / tween.duration
            value = tween.value_at(progress)
            changed = self._publish(value) or changed
            if progress < 1.0:
                return changed

            completed_at = active_start + tween.duration
            if self._index + 1 >= len(self.sequence.tweens):
                self.status = AnimationStatus.COMPLETED
                return changed

            self._index += 1
            self._segment_origin = completed_at
            self._last_value = None
            changed = self._publish(self.current_tween.start) or changed

        return changed

    def cancel(self, *, apply_final_value: bool = False) -> bool:
        """Cancel this sequence, optionally publishing the final chained value."""

        if not self.running:
            return False
        if apply_final_value:
            final_tween = self.sequence.tweens[-1]
            final_tween.update(final_tween.end)
            self._last_value = final_tween.end
            self._index = len(self.sequence.tweens) - 1
        self.status = AnimationStatus.CANCELLED
        return True

    def _publish(self, value: float) -> bool:
        if self._last_value == value:
            return False
        self.current_tween.update(value)
        self._last_value = value
        return True


class AnimationController:
    """Own and advance independent SwirUI animation sequences.

    Controllers can be ticked explicitly for deterministic simulations and tests or attached
    to an :class:`~swirui.app.App`. An attached controller advances from the application's
    measured ``frame_time`` and invalidates the next frame while work remains, so one
    animation timeline naturally follows the existing display-aware frame scheduler.
    """

    def __init__(self) -> None:
        self._handles: list[AnimationHandle] = []
        self._frame_unsubscribe: Callable[[], None] | None = None
        self._request_frame: Callable[[], None] | None = None

    @property
    def active(self) -> bool:
        return any(handle.running for handle in self._handles)

    @property
    def handles(self) -> tuple[AnimationHandle, ...]:
        return tuple(self._handles)

    def play(
        self,
        animation: Tween | AnimationSequence,
        *,
        start_time: float | None = None,
    ) -> AnimationHandle:
        """Start one tween or sequence and return its cancellation/status handle."""

        if isinstance(animation, AnimationSequence):
            sequence = animation
        else:
            sequence = AnimationSequence((animation,))
        handle = AnimationHandle(sequence).start(start_time)
        self._handles.append(handle)
        if self._request_frame is not None:
            self._request_frame()
        return handle

    def tick(self, now: float | None = None) -> bool:
        """Advance every running animation once and prune terminal handles."""

        changed = False
        retained: list[AnimationHandle] = []
        for handle in self._handles:
            changed = handle.tick(now) or changed
            if handle.running:
                retained.append(handle)
        self._handles = retained
        return changed

    def cancel_all(self, *, apply_final_value: bool = False) -> int:
        """Cancel every active sequence and return the number cancelled."""

        cancelled = 0
        for handle in self._handles:
            cancelled += int(handle.cancel(apply_final_value=apply_final_value))
        self._handles.clear()
        if cancelled and self._request_frame is not None:
            self._request_frame()
        return cancelled

    def attach(self, app: App) -> Callable[[], None]:
        """Drive this controller from ``App.frame_rendered`` events.

        The first ``play()`` requests a frame. Each rendered frame advances the absolute
        timeline and requests another frame when values changed or work remains. Calling the
        returned function detaches the controller without cancelling its animation handles.
        """

        self.detach()

        def request_frame() -> None:
            app.invalidate()

        def on_frame(event: Event) -> None:
            raw_frame_time = event.data.get("frame_time")
            if not isinstance(raw_frame_time, int | float):
                return
            changed = self.tick(float(raw_frame_time))
            if changed or self.active:
                app.invalidate()

        self._request_frame = request_frame
        self._frame_unsubscribe = app.on("frame_rendered", on_frame)
        if self.active:
            app.invalidate()
        return self.detach

    def detach(self) -> None:
        """Stop application-driven ticking while preserving current handles."""

        if self._frame_unsubscribe is not None:
            self._frame_unsubscribe()
        self._frame_unsubscribe = None
        self._request_frame = None


class _OpacityTarget(Protocol):
    opacity: float


class _BoundsTarget(Protocol):
    bounds: Rect


def animate_opacity(
    target: _OpacityTarget,
    to: float,
    *,
    duration: float,
    easing: EasingFunction = ease_in_out_cubic,
    delay: float = 0.0,
) -> Tween:
    """Build an opacity tween for a retained widget-like target."""

    destination = float(to)
    if not 0.0 <= destination <= 1.0:
        raise ValueError("Opacity animation target must be between 0.0 and 1.0.")
    return Tween(
        start=float(target.opacity),
        end=destination,
        duration=duration,
        delay=delay,
        easing=easing,
        update=lambda value: setattr(target, "opacity", value),
    )


def animate_bounds(
    target: _BoundsTarget,
    to: Rect,
    *,
    duration: float,
    easing: EasingFunction = ease_in_out_cubic,
    delay: float = 0.0,
) -> Tween:
    """Build one geometry tween that can express retained slide/scale transitions."""

    start = target.bounds

    def update(progress: float) -> None:
        target.bounds = Rect(
            start.x + (to.x - start.x) * progress,
            start.y + (to.y - start.y) * progress,
            start.width + (to.width - start.width) * progress,
            start.height + (to.height - start.height) * progress,
        )

    return Tween(
        start=0.0,
        end=1.0,
        duration=duration,
        delay=delay,
        easing=easing,
        update=update,
    )
