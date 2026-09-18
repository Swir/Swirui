"""Frame-rate-independent retained fade, slide and scale transitions for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering.geometry import Point

if TYPE_CHECKING:
    from .widgets.base import Widget


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
        """Start or restart from ``from_opacity``."""

        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance using elapsed seconds and return any unused completion tail."""

        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        """Cancel while retaining the currently presented opacity sample."""

        return self._tween.cancel()

    def restore(self) -> None:
        """Restore opacity captured when this transition was created."""

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
    testing, through the already verified retained SceneGraph translation path.
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
        """Start or restart from ``from_offset`` relative to the captured base."""

        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance using elapsed seconds and return any unused completion tail."""

        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        """Cancel while retaining the currently presented offset sample."""

        return self._tween.cancel()

    def restore(self) -> None:
        """Restore the visual offset captured when this transition was created."""

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
    """Animate uniform post-layout scale for a complete retained widget subtree.

    Scale is applied around the root widget's visual center during SceneGraph
    compilation. Authored layout bounds and intrinsic measurement remain unchanged;
    descendants, path geometry, corner radii, shaped-text metrics, clipping and hit
    testing all consume the same transformed retained geometry.
    """

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
        """Start or restart from ``from_scale``."""

        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance using elapsed seconds and return any unused completion tail."""

        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        """Cancel while retaining the currently presented scale sample."""

        return self._tween.cancel()

    def restore(self) -> None:
        """Restore scale captured when this transition was created."""

        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.visual_scale = self._authored_scale

    def _apply(self, value: float) -> None:
        self.widget.visual_scale = value


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


def _opacity(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be finite and between 0.0 and 1.0.")
    return normalized
