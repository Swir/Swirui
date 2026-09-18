"""Frame-rate-independent retained shared-element transitions for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering.geometry import Point

if TYPE_CHECKING:
    from .widgets.base import Widget


class SharedElementTransition:
    """Cross-fade and move two retained widgets along one shared visual path.

    The transition treats ``source`` and ``target`` as two retained representations
    of the same logical element. Their authored layout bounds are never mutated.
    Instead, the target starts visually aligned to the source while the source moves
    toward the target. Both therefore occupy the same visual center for every sample
    and cross-fade on top of each other until the target reaches its authored state.

    Existing ``visual_offset`` values are preserved as part of the authored visual
    state. Scene compilation applies the sampled offsets to the full retained subtree,
    so clipping and hit testing follow the transition without recreating the native
    window or persistent GPU context.
    """

    def __init__(
        self,
        source: Widget,
        target: Widget,
        *,
        duration: float = 0.32,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if source is target:
            raise ValueError("SharedElementTransition requires distinct source and target widgets.")

        self.source = source
        self.target = target
        self.duration = _non_negative("duration", duration)
        self.easing = easing
        self._source_opacity = source.opacity
        self._target_opacity = target.opacity
        self._source_offset = source.visual_offset
        self._target_offset = target.visual_offset
        self._delta = _visual_center_delta(source, target)
        self._tween = Tween(
            0.0,
            1.0,
            self.duration,
            self._apply_progress,
            easing=self.easing,
            on_complete=on_complete,
        )

    @property
    def status(self) -> AnimationStatus:
        return self._tween.status

    @property
    def elapsed(self) -> float:
        return self._tween.elapsed

    @property
    def progress(self) -> float:
        return self._tween.progress

    def start(self) -> SharedElementTransition:
        """Start or restart from the captured authored visual states."""

        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance by elapsed seconds and return any unused completion tail."""

        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        """Cancel while retaining the currently presented visual sample."""

        return self._tween.cancel()

    def restore(self) -> None:
        """Restore source and target opacity/offset captured at construction."""

        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.source.opacity = self._source_opacity
        self.target.opacity = self._target_opacity
        self.source.visual_offset = self._source_offset
        self.target.visual_offset = self._target_offset

    def _apply_progress(self, progress: float) -> None:
        alpha = min(1.0, max(0.0, progress))
        delta = self._delta
        source_offset = self._source_offset
        target_offset = self._target_offset

        self.source.opacity = self._source_opacity * (1.0 - alpha)
        self.target.opacity = self._target_opacity * alpha
        self.source.visual_offset = Point(
            source_offset.x + delta.x * progress,
            source_offset.y + delta.y * progress,
        )
        self.target.visual_offset = Point(
            target_offset.x - delta.x * (1.0 - progress),
            target_offset.y - delta.y * (1.0 - progress),
        )


def _visual_center_delta(source: Widget, target: Widget) -> Point:
    source_center = Point(
        source.bounds.x + source.bounds.width * 0.5 + source.visual_offset.x,
        source.bounds.y + source.bounds.height * 0.5 + source.visual_offset.y,
    )
    target_center = Point(
        target.bounds.x + target.bounds.width * 0.5 + target.visual_offset.x,
        target.bounds.y + target.bounds.height * 0.5 + target.visual_offset.y,
    )
    delta = Point(target_center.x - source_center.x, target_center.y - source_center.y)
    if not math.isfinite(delta.x) or not math.isfinite(delta.y):
        raise ValueError("Shared-element visual centers must be finite.")
    return delta


def _non_negative(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized
