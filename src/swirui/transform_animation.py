"""Retained visual-property transitions for SwirUI widgets."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering.geometry import Point

if TYPE_CHECKING:
    from .widgets.base import Widget


class FadeTransition:
    """Animate a retained widget's opacity without changing layout geometry."""

    def __init__(
        self,
        widget: Widget,
        to_opacity: float,
        *,
        duration: float = 0.22,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self.to_opacity = _opacity("to_opacity", to_opacity)
        self.easing = easing
        self._original = widget.opacity
        self._tween = Tween(
            self._original,
            self.to_opacity,
            self.duration,
            self._apply,
            easing=easing,
            on_complete=on_complete,
        )

    @property
    def status(self) -> AnimationStatus:
        return self._tween.status

    @property
    def progress(self) -> float:
        return self._tween.progress

    @property
    def elapsed(self) -> float:
        return self._tween.elapsed

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
        self.widget.opacity = self._original

    def _apply(self, value: float) -> None:
        self.widget.opacity = value


class SlideTransition:
    """Animate a widget's visual-only logical-DIP offset."""

    def __init__(
        self,
        widget: Widget,
        to_offset: Point,
        *,
        duration: float = 0.24,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if not math.isfinite(to_offset.x) or not math.isfinite(to_offset.y):
            raise ValueError("to_offset coordinates must be finite.")
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self.to_offset = to_offset
        self.easing = easing
        self._original = widget.visual_offset
        self._x = Tween(
            self._original.x,
            to_offset.x,
            self.duration,
            self._apply_x,
            easing=easing,
            on_complete=on_complete,
        )
        self._from_y = self._original.y
        self._to_y = to_offset.y

    @property
    def status(self) -> AnimationStatus:
        return self._x.status

    @property
    def progress(self) -> float:
        return self._x.progress

    @property
    def elapsed(self) -> float:
        return self._x.elapsed

    def start(self) -> SlideTransition:
        self._x.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._x.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._x.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._x.cancel()
        self.widget.visual_offset = self._original

    def _apply_x(self, x: float) -> None:
        span = self.to_offset.x - self._original.x
        progress = 1.0 if span == 0.0 else (x - self._original.x) / span
        progress = min(1.0, max(0.0, progress))
        y = self._from_y + (self._to_y - self._from_y) * progress
        self.widget.visual_offset = Point(x, y)


class ScaleTransition:
    """Animate a uniform visual scale around the retained widget's center.

    Scaling is applied after layout and before the widget's visual translation. The
    authored ``bounds`` and ``preferred_size`` therefore remain untouched while the
    complete compiled subtree, including shaped text, images, paths, clipping and hit
    testing, follows the sampled scale.
    """

    def __init__(
        self,
        widget: Widget,
        to_scale: float,
        *,
        duration: float = 0.24,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self.to_scale = _scale("to_scale", to_scale)
        self.easing = easing
        self._original = widget.visual_scale
        self._tween = Tween(
            self._original,
            self.to_scale,
            self.duration,
            self._apply,
            easing=easing,
            on_complete=on_complete,
        )

    @property
    def status(self) -> AnimationStatus:
        return self._tween.status

    @property
    def progress(self) -> float:
        return self._tween.progress

    @property
    def elapsed(self) -> float:
        return self._tween.elapsed

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
        self.widget.visual_scale = self._original

    def _apply(self, value: float) -> None:
        self.widget.visual_scale = value


def _non_negative(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized


def _opacity(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be finite and between 0.0 and 1.0.")
    return normalized


def _scale(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized
