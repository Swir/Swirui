"""Frame scheduling primitives for SwirUI render loops."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FrameStats:
    frame_number: int = 0
    last_frame_time: float | None = None
    dropped_requests: int = 0


class FrameScheduler:
    """Invalidation-driven frame scheduler with a configurable FPS ceiling.

    The scheduler is clock-agnostic: platform backends provide monotonic time,
    which keeps the core deterministic and easy to test.
    """

    def __init__(self, target_fps: int = 60) -> None:
        self._target_fps = 0
        self._frame_interval = 0.0
        self.target_fps = target_fps
        self._dirty = True
        self.stats = FrameStats()

    @property
    def target_fps(self) -> int:
        return self._target_fps

    @target_fps.setter
    def target_fps(self, value: int) -> None:
        if value <= 0:
            raise ValueError("target_fps must be positive.")
        self._target_fps = value
        self._frame_interval = 1.0 / value

    @property
    def frame_interval(self) -> float:
        return self._frame_interval

    @property
    def dirty(self) -> bool:
        return self._dirty

    def invalidate(self) -> None:
        self._dirty = True

    def is_due(self, now: float) -> bool:
        if now < 0:
            raise ValueError("Frame time cannot be negative.")
        if not self._dirty:
            return False
        last = self.stats.last_frame_time
        return last is None or now - last >= self._frame_interval

    def consume(self, now: float) -> bool:
        """Consume a pending frame request if its frame interval has elapsed."""

        if not self.is_due(now):
            if self._dirty:
                self.stats.dropped_requests += 1
            return False
        self._dirty = False
        self.stats.frame_number += 1
        self.stats.last_frame_time = now
        return True

    def seconds_until_due(self, now: float) -> float | None:
        """Return time until the next pending frame, or ``None`` if clean."""

        if now < 0:
            raise ValueError("Frame time cannot be negative.")
        if not self._dirty:
            return None
        last = self.stats.last_frame_time
        if last is None:
            return 0.0
        return max(0.0, self._frame_interval - (now - last))
