"""Frame-rate-independent retained page transitions for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering.geometry import Point

if TYPE_CHECKING:
    from .widgets.base import Widget


class PageTransitionDirection(StrEnum):
    """Direction in which the outgoing page leaves the viewport."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


class PageTransition:
    """Cross-fade and slide between two retained widgets.

    The transition changes only visual properties: opacity and ``visual_offset``.
    Layout geometry therefore remains stable while the compiled retained subtrees,
    clipping and hit testing follow the animated offsets. The incoming widget starts
    displaced opposite the outgoing direction and reaches its authored visual state
    at completion.

    The object implements SwirUI's animation-playable contract and can be passed
    directly to :class:`~swirui.animation.AnimationController`.
    """

    def __init__(
        self,
        outgoing: Widget,
        incoming: Widget,
        *,
        duration: float = 0.28,
        distance: float = 48.0,
        direction: PageTransitionDirection = PageTransitionDirection.LEFT,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if outgoing is incoming:
            raise ValueError("PageTransition requires distinct outgoing and incoming widgets.")
        self.outgoing = outgoing
        self.incoming = incoming
        self.duration = _non_negative("duration", duration)
        self.distance = _non_negative("distance", distance)
        self.direction = PageTransitionDirection(direction)
        self.easing = easing
        self._outgoing_opacity = outgoing.opacity
        self._incoming_opacity = incoming.opacity
        self._outgoing_offset = outgoing.visual_offset
        self._incoming_offset = incoming.visual_offset
        self._vector = _direction_vector(self.direction, self.distance)
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

    def start(self) -> PageTransition:
        """Restart from the authored outgoing/incoming visual states."""

        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance by elapsed seconds and return any unused completion tail."""

        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        """Cancel while retaining the currently presented visual sample."""

        return self._tween.cancel()

    def restore(self) -> None:
        """Restore both widgets to the visual state captured at construction."""

        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.outgoing.opacity = self._outgoing_opacity
        self.incoming.opacity = self._incoming_opacity
        self.outgoing.visual_offset = self._outgoing_offset
        self.incoming.visual_offset = self._incoming_offset

    def _apply_progress(self, progress: float) -> None:
        vector = self._vector
        outgoing_offset = self._outgoing_offset
        incoming_offset = self._incoming_offset
        self.outgoing.opacity = self._outgoing_opacity * (1.0 - progress)
        self.incoming.opacity = self._incoming_opacity * progress
        self.outgoing.visual_offset = Point(
            outgoing_offset.x + vector.x * progress,
            outgoing_offset.y + vector.y * progress,
        )
        self.incoming.visual_offset = Point(
            incoming_offset.x - vector.x * (1.0 - progress),
            incoming_offset.y - vector.y * (1.0 - progress),
        )


def _direction_vector(direction: PageTransitionDirection, distance: float) -> Point:
    if direction is PageTransitionDirection.LEFT:
        return Point(-distance, 0.0)
    if direction is PageTransitionDirection.RIGHT:
        return Point(distance, 0.0)
    if direction is PageTransitionDirection.UP:
        return Point(0.0, -distance)
    return Point(0.0, distance)


def _non_negative(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized
