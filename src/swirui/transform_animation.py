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


class RevealTransition:
    """Reveal a retained widget by combining visual-only scale and opacity.

    The widget starts from ``from_scale`` and ``from_opacity`` relative to its
    captured authored visual state, then resolves to the exact captured scale and
    opacity. Layout bounds are never mutated, so the transition can be driven by the
    same retained frame clock as other SwirUI animations.
    """

    def __init__(
        self,
        widget: Widget,
        *,
        from_scale: float = 0.92,
        from_opacity: float = 0.0,
        duration: float = 0.24,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.from_scale = _scale("from_scale", from_scale)
        self.from_opacity = _opacity("from_opacity", from_opacity)
        self.duration = _non_negative("duration", duration)
        self.easing = easing
        self._original_scale = widget.visual_scale
        self._original_opacity = widget.opacity
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
        self.widget.visual_scale = self._original_scale
        self.widget.opacity = self._original_opacity

    def _apply_progress(self, progress: float) -> None:
        alpha = _unit_interval(progress)
        scale_factor = self.from_scale + (1.0 - self.from_scale) * alpha
        opacity_factor = self.from_opacity + (1.0 - self.from_opacity) * alpha
        self.widget.visual_scale = self._original_scale * scale_factor
        self.widget.opacity = self._original_opacity * opacity_factor


class FlipTransition:
    """Perform a retained center-collapse flip with an optional midpoint swap.

    SwirUI's initial flip contract intentionally uses the already-verified uniform
    visual-scale path rather than introducing an unverified pseudo-3D transform.
    The widget collapses to its center, invokes ``on_midpoint`` once while visually
    hidden, then expands back to its captured scale. The complete retained subtree
    follows the transition and layout geometry remains stable.
    """

    def __init__(
        self,
        widget: Widget,
        *,
        duration: float = 0.32,
        easing: Easing = ease_in_out_cubic,
        on_midpoint: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self.easing = easing
        self.on_midpoint = on_midpoint
        self._original_scale = widget.visual_scale
        self._midpoint_fired = False
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

    def start(self) -> FlipTransition:
        self._midpoint_fired = False
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.visual_scale = self._original_scale

    def _apply_progress(self, progress: float) -> None:
        alpha = _unit_interval(progress)
        self.widget.visual_scale = self._original_scale * abs(1.0 - 2.0 * alpha)
        if alpha >= 0.5 and not self._midpoint_fired:
            self._midpoint_fired = True
            if self.on_midpoint is not None:
                self.on_midpoint()


class MorphTransition:
    """Morph matching-aspect retained elements through one visual geometry path.

    ``source`` and ``target`` remain in their authored layouts. Their visual centers,
    uniform scales and opacity are sampled so both representations overlap throughout
    the transition while source geometry grows/shrinks into target geometry. The
    initial contract requires positive same-aspect bounds because SwirUI deliberately
    avoids distorting shaped text or images with unverified non-uniform scaling.
    """

    _ASPECT_REL_TOL = 1.0e-4
    _ASPECT_ABS_TOL = 1.0e-6

    def __init__(
        self,
        source: Widget,
        target: Widget,
        *,
        duration: float = 0.36,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if source is target:
            raise ValueError("MorphTransition requires distinct source and target widgets.")

        self.source = source
        self.target = target
        self.duration = _non_negative("duration", duration)
        self.easing = easing
        self._source_opacity = source.opacity
        self._target_opacity = target.opacity
        self._source_offset = source.visual_offset
        self._target_offset = target.visual_offset
        self._source_scale = _positive_scale("source.visual_scale", source.visual_scale)
        self._target_scale = _positive_scale("target.visual_scale", target.visual_scale)
        self._scale_ratio = _visual_scale_ratio(source, target)
        self._delta = _visual_center_delta(source, target)
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

    def start(self) -> MorphTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.source.opacity = self._source_opacity
        self.target.opacity = self._target_opacity
        self.source.visual_offset = self._source_offset
        self.target.visual_offset = self._target_offset
        self.source.visual_scale = self._source_scale
        self.target.visual_scale = self._target_scale

    def _apply_progress(self, progress: float) -> None:
        alpha = _unit_interval(progress)
        delta = self._delta
        ratio = self._scale_ratio

        self.source.opacity = self._source_opacity * (1.0 - alpha)
        self.target.opacity = self._target_opacity * alpha
        self.source.visual_offset = Point(
            self._source_offset.x + delta.x * alpha,
            self._source_offset.y + delta.y * alpha,
        )
        self.target.visual_offset = Point(
            self._target_offset.x - delta.x * (1.0 - alpha),
            self._target_offset.y - delta.y * (1.0 - alpha),
        )
        self.source.visual_scale = self._source_scale * (1.0 + (ratio - 1.0) * alpha)
        target_start_scale = self._target_scale / ratio
        self.target.visual_scale = target_start_scale + (
            self._target_scale - target_start_scale
        ) * alpha


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
        raise ValueError("Morph visual centers must be finite.")
    return delta


def _visual_scale_ratio(source: Widget, target: Widget) -> float:
    source_width = source.bounds.width * source.visual_scale
    source_height = source.bounds.height * source.visual_scale
    target_width = target.bounds.width * target.visual_scale
    target_height = target.bounds.height * target.visual_scale
    if min(source_width, source_height, target_width, target_height) <= 0.0:
        raise ValueError("MorphTransition requires positive visual dimensions.")

    width_ratio = target_width / source_width
    height_ratio = target_height / source_height
    if not math.isclose(
        width_ratio,
        height_ratio,
        rel_tol=MorphTransition._ASPECT_REL_TOL,
        abs_tol=MorphTransition._ASPECT_ABS_TOL,
    ):
        raise ValueError(
            "MorphTransition requires source and target to have matching visual aspect ratios."
        )
    return (width_ratio + height_ratio) * 0.5


def _unit_interval(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


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


def _positive_scale(name: str, value: float) -> float:
    normalized = _scale(name, value)
    if normalized <= 0.0:
        raise ValueError(f"{name} must be greater than zero for morphing.")
    return normalized
