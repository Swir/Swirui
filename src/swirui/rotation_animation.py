"""Retained rotation transition for SwirUI widgets."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic

if TYPE_CHECKING:
    from .widgets.base import Widget


class RotateTransition:
    """Animate a retained widget's visual-only rotation in radians.

    Rotation is applied after layout, visual scale and visual translation. The
    complete retained subtree receives one center-origin affine transform so hit
    testing and renderer traversal share the same transform contract.
    """

    def __init__(
        self,
        widget: Widget,
        to_radians: float,
        *,
        duration: float = 0.24,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.widget = widget
        self.duration = _non_negative("duration", duration)
        self.to_radians = _finite("to_radians", to_radians)
        self.easing = easing
        self._original = widget.visual_rotation
        self._tween = Tween(
            self._original,
            self.to_radians,
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

    def start(self) -> RotateTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def restore(self) -> None:
        if self.status is AnimationStatus.RUNNING:
            self._tween.cancel()
        self.widget.visual_rotation = self._original

    def _apply(self, value: float) -> None:
        self.widget.visual_rotation = value


def _finite(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


def _non_negative(name: str, value: float) -> float:
    normalized = _finite(name, value)
    if normalized < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return normalized
