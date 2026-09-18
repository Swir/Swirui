"""Deterministic scalar keyframe animation primitives for SwirUI."""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .animation import AnimationPlayable, AnimationSequence, AnimationStatus, Easing, linear


@dataclass(frozen=True, slots=True)
class Keyframe:
    """One normalized-time scalar keyframe.

    ``offset`` is expressed in the inclusive ``0.0..1.0`` animation timeline and
    ``easing`` controls interpolation from this keyframe to the next one. Values and
    offsets must be finite so the retained animation clock can remain deterministic.
    """

    offset: float
    value: float
    easing: Easing = linear

    def __post_init__(self) -> None:
        offset = float(self.offset)
        value = float(self.value)
        if not math.isfinite(offset) or not 0.0 <= offset <= 1.0:
            raise ValueError("Keyframe offset must be finite and between 0.0 and 1.0.")
        if not math.isfinite(value):
            raise ValueError("Keyframe value must be finite.")
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "value", value)


class KeyframeAnimation:
    """Animate a scalar across multiple deterministic elapsed-time keyframes.

    The first keyframe must be at offset ``0.0`` and the last at ``1.0``. Intermediate
    offsets must increase strictly. Each keyframe's easing function shapes the segment
    that starts at that frame and ends at the next frame. ``advance()`` uses elapsed
    seconds and returns any unused positive frame tail, matching :class:`Tween` and
    allowing lossless composition inside :class:`AnimationSequence`.
    """

    def __init__(
        self,
        keyframes: Sequence[Keyframe],
        duration: float,
        update: Callable[[float], None],
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        frames = tuple(keyframes)
        if len(frames) < 2:
            raise ValueError("KeyframeAnimation requires at least two keyframes.")
        if frames[0].offset != 0.0:
            raise ValueError("The first keyframe offset must be 0.0.")
        if frames[-1].offset != 1.0:
            raise ValueError("The last keyframe offset must be 1.0.")
        if any(
            current.offset >= following.offset
            for current, following in zip(frames, frames[1:], strict=False)
        ):
            raise ValueError("Keyframe offsets must increase strictly.")

        normalized_duration = float(duration)
        if not math.isfinite(normalized_duration) or normalized_duration < 0.0:
            raise ValueError("duration must be finite and non-negative.")

        self.keyframes = frames
        self.duration = normalized_duration
        self.update = update
        self.on_complete = on_complete
        self._offsets = tuple(frame.offset for frame in frames)
        self._elapsed = 0.0
        self._value = frames[0].value
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

    @property
    def value(self) -> float:
        return self._value

    def start(self) -> KeyframeAnimation:
        """Start or restart from the authored first keyframe."""

        self._elapsed = 0.0
        self._status = AnimationStatus.RUNNING
        self._publish(self.keyframes[0].value)
        if self.duration == 0.0:
            self._finish()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance by elapsed seconds and return any unconsumed positive tail."""

        delta = float(delta_seconds)
        if not math.isfinite(delta) or delta < 0.0:
            raise ValueError("delta_seconds must be finite and non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return delta

        remaining_duration = max(0.0, self.duration - self._elapsed)
        consumed = min(delta, remaining_duration)
        self._elapsed += consumed

        if self._elapsed >= self.duration:
            self._finish()
            return max(0.0, delta - consumed)

        self._publish(self.value_at(self._elapsed / self.duration))
        return max(0.0, delta - consumed)

    def cancel(self) -> bool:
        """Cancel at the currently published value without forcing completion."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        self._status = AnimationStatus.CANCELLED
        return True

    def then(self, *animations: AnimationPlayable) -> AnimationSequence:
        """Build a serial animation sequence beginning with this keyframe animation."""

        return AnimationSequence(self, *animations)

    def value_at(self, progress: float) -> float:
        """Sample the authored keyframe curve at normalized timeline progress."""

        normalized = float(progress)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError("progress must be finite and between 0.0 and 1.0.")
        if normalized <= 0.0:
            return self.keyframes[0].value
        if normalized >= 1.0:
            return self.keyframes[-1].value

        index = bisect.bisect_right(self._offsets, normalized) - 1
        start = self.keyframes[index]
        end = self.keyframes[index + 1]
        segment_progress = (normalized - start.offset) / (end.offset - start.offset)
        eased = float(start.easing(segment_progress))
        if not math.isfinite(eased):
            raise ValueError("Keyframe easing result must be finite.")
        return start.value + (end.value - start.value) * eased

    def _publish(self, value: float) -> None:
        if not math.isfinite(value):
            raise ValueError("Keyframe animation value must be finite.")
        self._value = value
        self.update(value)

    def _finish(self) -> None:
        self._elapsed = self.duration
        self._publish(self.keyframes[-1].value)
        self._status = AnimationStatus.COMPLETED
        if self.on_complete is not None:
            self.on_complete()
