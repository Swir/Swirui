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
        self._tween = Tween(
            0.0,
            1.0,
            self.duration,
            self._apply_progress,
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
        self.widget.visual_offset = self._original

    def _apply_progress(self, progress: float) -> None:
        self.widget.visual_offset = Point(
            self._original.x + (self.to_offset.x - self._original.x) * progress,
            self._original.y + (self.to_offset.y - self._original.y) * progress,
        )


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
