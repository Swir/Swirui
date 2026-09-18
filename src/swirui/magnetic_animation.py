"""Pointer-driven magnetic interaction animation for retained SwirUI widgets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .animation import AnimationController, AnimationParallel, AnimationStatus, SpringAnimation
from .core import Event
from .rendering import Point
from .widgets.base import Widget


@dataclass(frozen=True, slots=True)
class MagneticInteractionSpec:
    """Strength, travel limit and release spring for magnetic interactions."""

    strength: float = 0.22
    max_offset: float = 18.0
    mass: float = 1.0
    stiffness: float = 240.0
    damping: float = 30.0
    settle_threshold: float = 0.01
    max_duration: float = 1.25

    def __post_init__(self) -> None:
        _non_negative("strength", self.strength)
        _non_negative("max_offset", self.max_offset)
        _positive("mass", self.mass)
        _positive("stiffness", self.stiffness)
        _non_negative("damping", self.damping)
        _positive("settle_threshold", self.settle_threshold)
        _positive("max_duration", self.max_duration)


class MagneticInteractionAnimator:
    """Pull a retained widget toward the pointer and spring it back on release.

    Pointer attraction writes only :attr:`~swirui.widgets.base.Widget.visual_offset`,
    so authored/layout geometry and intrinsic measurement stay unchanged. The runtime
    applies that offset to the compiled SceneGraph subtree, keeping rendering, clipping
    and hit testing aligned without recreating the native window or GPU context.

    Pointer movement is immediate for low input latency. Leaving or disabling the widget
    returns both axes to zero with analytical :class:`SpringAnimation` instances driven by
    the existing window-scoped :class:`AnimationController`.
    """

    def __init__(
        self,
        controller: AnimationController,
        widget: Widget,
        *,
        spec: MagneticInteractionSpec | None = None,
    ) -> None:
        self.controller = controller
        self.widget = widget
        self.spec = spec or MagneticInteractionSpec()
        self._release: AnimationParallel | None = None
        self._disposed = False
        self._unsubscribers = (
            widget.on("pointer_move", self._on_pointer_move),
            widget.on("pointer_leave", self._on_pointer_leave),
            widget.on("invalidated", self._on_invalidated),
        )

    @property
    def active(self) -> bool:
        """Return whether a spring-back animation is currently running."""

        release = self._release
        return release is not None and release.status is AnimationStatus.RUNNING

    @property
    def disposed(self) -> bool:
        return self._disposed

    @property
    def offset(self) -> Point:
        return self.widget.visual_offset

    def dispose(self, *, restore: bool = True) -> None:
        """Detach listeners, cancel release motion and optionally restore zero offset."""

        if self._disposed:
            return
        self._disposed = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._cancel_release()
        if restore:
            self.widget.visual_offset = Point()

    def _on_pointer_move(self, event: Event) -> None:
        if self._disposed or not self.widget.enabled:
            return
        position = _pointer_position(event.data.get("event"))
        if position is None:
            return
        self._cancel_release()
        pointer_x, pointer_y = position
        bounds = self.widget.bounds
        target_x = (pointer_x - (bounds.x + bounds.width / 2.0)) * self.spec.strength
        target_y = (pointer_y - (bounds.y + bounds.height / 2.0)) * self.spec.strength
        self.widget.visual_offset = _clamp_offset(target_x, target_y, self.spec.max_offset)

    def _on_pointer_leave(self, _event: Event) -> None:
        self._spring_home()

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.widget.enabled:
            self._spring_home()

    def _spring_home(self) -> None:
        if self._disposed:
            return
        self._cancel_release()
        current = self.widget.visual_offset
        if current == Point():
            return

        threshold = self.spec.settle_threshold
        release = AnimationParallel(
            SpringAnimation(
                current.x,
                0.0,
                self._set_x,
                mass=self.spec.mass,
                stiffness=self.spec.stiffness,
                damping=self.spec.damping,
                position_threshold=threshold,
                velocity_threshold=threshold,
                max_duration=self.spec.max_duration,
            ),
            SpringAnimation(
                current.y,
                0.0,
                self._set_y,
                mass=self.spec.mass,
                stiffness=self.spec.stiffness,
                damping=self.spec.damping,
                position_threshold=threshold,
                velocity_threshold=threshold,
                max_duration=self.spec.max_duration,
            ),
        )
        self._release = release
        self.controller.play(release)

    def _set_x(self, value: float) -> None:
        offset = self.widget.visual_offset
        self.widget.visual_offset = Point(value, offset.y)

    def _set_y(self, value: float) -> None:
        offset = self.widget.visual_offset
        self.widget.visual_offset = Point(offset.x, value)

    def _cancel_release(self) -> None:
        release = self._release
        if release is not None and release.status is AnimationStatus.RUNNING:
            release.cancel()
        self._release = None


def _pointer_position(platform_event: Any) -> tuple[float, float] | None:
    if platform_event is None:
        return None
    x = getattr(platform_event, "x", None)
    y = getattr(platform_event, "y", None)
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    normalized_x = float(x)
    normalized_y = float(y)
    if not math.isfinite(normalized_x) or not math.isfinite(normalized_y):
        return None
    return normalized_x, normalized_y


def _clamp_offset(x: float, y: float, limit: float) -> Point:
    if limit == 0.0:
        return Point()
    magnitude = math.hypot(x, y)
    if magnitude <= limit or magnitude == 0.0:
        return Point(x, y)
    scale = limit / magnitude
    return Point(x * scale, y * scale)


def _finite(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


def _positive(name: str, value: float) -> float:
    normalized = _finite(name, value)
    if normalized <= 0.0:
        raise ValueError(f"{name} must be positive.")
    return normalized


def _non_negative(name: str, value: float) -> float:
    normalized = _finite(name, value)
    if normalized < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return normalized
