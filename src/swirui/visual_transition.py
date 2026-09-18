"""Frame-rate-independent retained visual transitions for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering.geometry import Point, Rect

if TYPE_CHECKING:
    from .widgets.base import Widget


class RevealDirection(StrEnum):
    """Direction in which a retained reveal clip expands."""

    LEFT_TO_RIGHT = "left-to-right"
    RIGHT_TO_LEFT = "right-to-left"
    TOP_TO_BOTTOM = "top-to-bottom"
    BOTTOM_TO_TOP = "bottom-to-top"


class FadeTransition:
    """Animate widget opacity without changing layout geometry.

    ``from_opacity`` and ``to_opacity`` are absolute visual opacity values. Omitting
    either endpoint uses the opacity captured when the transition is created, which
    makes ``FadeTransition(widget, from_opacity=0.0)`` a convenient fade-in while
    preserving a non-1.0 authored opacity. ``restore()`` always restores that captured
    visual state.
    """

    def __init__(
        self,
        widget: Widget,
        *,
        from_opacity: float | None = None,
        to_opacity: float | None = None,
        duration: float = 0.22,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self._authored_opacity = widget.opacity
        self.from_opacity = _opacity(
            "from_opacity",
            self._authored_opacity if from_opacity is None else from_opacity,
        )
        self.to_opacity = _opacity(
            "to_opacity",
            self._authored_opacity if to_opacity is None else to_opacity,
        )
        self.easing = easing
        self._tween = Tween(
            self.from_opacity,
            self.to_opacity,
            self.duration,
            self._apply,
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

    def start(self) -> FadeTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.opacity = self._authored_opacity

    def _apply(self, value: float) -> None:
        self.widget.opacity = value


class SlideTransition:
    """Animate a retained widget's post-layout visual offset.

    Endpoints are deltas relative to the widget's ``visual_offset`` captured at
    construction. This preserves authored layout bounds and any pre-existing visual
    offset while moving the complete compiled subtree, including clipping and hit
    testing, through the retained SceneGraph translation path.
    """

    def __init__(
        self,
        widget: Widget,
        *,
        from_offset: Point = Point(),
        to_offset: Point = Point(),
        duration: float = 0.24,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self.from_offset = _finite_point("from_offset", from_offset)
        self.to_offset = _finite_point("to_offset", to_offset)
        self.easing = easing
        self._authored_offset = widget.visual_offset
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

    def start(self) -> SlideTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.visual_offset = self._authored_offset

    def _apply_progress(self, progress: float) -> None:
        base = self._authored_offset
        self.widget.visual_offset = Point(
            base.x + self.from_offset.x + (self.to_offset.x - self.from_offset.x) * progress,
            base.y + self.from_offset.y + (self.to_offset.y - self.from_offset.y) * progress,
        )


class ScaleTransition:
    """Animate uniform post-layout scale for a complete retained widget subtree."""

    def __init__(
        self,
        widget: Widget,
        *,
        from_scale: float = 0.92,
        to_scale: float | None = None,
        duration: float = 0.22,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self._authored_scale = widget.visual_scale
        self.from_scale = _positive("from_scale", from_scale)
        self.to_scale = _positive(
            "to_scale",
            self._authored_scale if to_scale is None else to_scale,
        )
        self.easing = easing
        self._tween = Tween(
            self.from_scale,
            self.to_scale,
            self.duration,
            self._apply,
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

    def start(self) -> ScaleTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.visual_scale = self._authored_scale

    def _apply(self, value: float) -> None:
        self.widget.visual_scale = value


class RevealTransition:
    """Reveal a retained subtree with an animated visual-only rectangular clip.

    The clip is derived from the widget's authored bounds for every elapsed-time
    sample. Existing ``visual_clip`` state is intersected rather than discarded and
    is restored when the transition reaches a fully revealed state or ``restore()``
    is called. Because the clip is part of the retained scene, GPU painting and hit
    testing share the same visible region.
    """

    def __init__(
        self,
        widget: Widget,
        *,
        direction: RevealDirection = RevealDirection.LEFT_TO_RIGHT,
        from_progress: float = 0.0,
        to_progress: float = 1.0,
        duration: float = 0.28,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.direction = RevealDirection(direction)
        self.from_progress = _unit_interval("from_progress", from_progress)
        self.to_progress = _unit_interval("to_progress", to_progress)
        self.duration = _non_negative("duration", duration)
        self.easing = easing
        self._authored_clip = widget.visual_clip
        self._tween = Tween(
            self.from_progress,
            self.to_progress,
            self.duration,
            self._apply,
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

    def start(self) -> RevealTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.visual_clip = self._authored_clip

    def _apply(self, progress: float) -> None:
        if progress >= 1.0:
            self.widget.visual_clip = self._authored_clip
            return
        reveal = _reveal_rect(self.widget.bounds, self.direction, progress)
        if self._authored_clip is None:
            self.widget.visual_clip = reveal
            return
        intersection = reveal.intersection(self._authored_clip)
        self.widget.visual_clip = (
            intersection
            if intersection is not None
            else Rect(reveal.x, reveal.y, 0.0, 0.0)
        )


def _reveal_rect(bounds: Rect, direction: RevealDirection, progress: float) -> Rect:
    if direction is RevealDirection.LEFT_TO_RIGHT:
        return Rect(bounds.x, bounds.y, bounds.width * progress, bounds.height)
    if direction is RevealDirection.RIGHT_TO_LEFT:
        width = bounds.width * progress
        return Rect(bounds.right - width, bounds.y, width, bounds.height)
    if direction is RevealDirection.TOP_TO_BOTTOM:
        return Rect(bounds.x, bounds.y, bounds.width, bounds.height * progress)
    height = bounds.height * progress
    return Rect(bounds.x, bounds.bottom - height, bounds.width, height)


def _finite_point(name: str, point: Point) -> Point:
    if not math.isfinite(point.x) or not math.isfinite(point.y):
        raise ValueError(f"{name} coordinates must be finite.")
    return point


def _non_negative(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized


def _positive(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero.")
    return normalized


def _unit_interval(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be finite and between 0.0 and 1.0.")
    return normalized


def _opacity(name: str, value: float) -> float:
    return _unit_interval(name, value)
