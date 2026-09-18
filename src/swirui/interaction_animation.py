"""Event-driven interaction animation helpers for retained widgets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .animation import (
    AnimationController,
    AnimationStatus,
    Easing,
    SpringAnimation,
    Tween,
    ease_out_cubic,
)
from .core import Event
from .rendering.geometry import Point

if TYPE_CHECKING:
    from .widgets.base import Widget


class InteractionPhase(StrEnum):
    """Resolved visual interaction state for :class:`InteractionAnimator`."""

    IDLE = "idle"
    HOVERED = "hovered"
    PRESSED = "pressed"
    FOCUSED = "focused"


@dataclass(frozen=True, slots=True)
class InteractionAnimationSpec:
    """Opacity targets and timing used by event-driven widget interaction animation."""

    hover_opacity: float = 0.96
    pressed_opacity: float = 0.82
    focus_opacity: float = 0.92
    duration: float = 0.10
    release_duration: float = 0.16

    def __post_init__(self) -> None:
        _opacity("hover_opacity", self.hover_opacity)
        _opacity("pressed_opacity", self.pressed_opacity)
        _opacity("focus_opacity", self.focus_opacity)
        _duration("duration", self.duration)
        _duration("release_duration", self.release_duration)


class InteractionAnimator:
    """Animate a retained widget across hover, press and focus transitions.

    The helper subscribes to the framework's routed interaction events and drives the
    widget's existing retained opacity through :class:`~swirui.animation.Tween` on a
    window-scoped :class:`~swirui.animation.AnimationController`. Rapid state changes
    cancel the superseded tween and restart from the currently presented opacity, so
    pointer/focus churn cannot snap back to an authored endpoint.

    ``pressed`` has the highest priority, followed by ``hovered`` and then ``focused``.
    Disabling the widget clears transient interaction state and returns to the authored
    idle opacity. ``dispose()`` detaches every listener and can restore that idle value.
    """

    def __init__(
        self,
        controller: AnimationController,
        widget: Widget,
        *,
        spec: InteractionAnimationSpec | None = None,
        easing: Easing = ease_out_cubic,
    ) -> None:
        self.controller = controller
        self.widget = widget
        self.spec = spec or InteractionAnimationSpec()
        self.easing = easing
        self._idle_opacity = _opacity("widget.opacity", widget.opacity)
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._phase = InteractionPhase.IDLE
        self._animation: Tween | None = None
        self._disposed = False
        self._unsubscribers = (
            widget.on("pointer_enter", self._on_pointer_enter),
            widget.on("pointer_leave", self._on_pointer_leave),
            widget.on("pointer_down", self._on_pointer_down),
            widget.on("pointer_up", self._on_pointer_up),
            widget.on("focus_gained", self._on_focus_gained),
            widget.on("focus_lost", self._on_focus_lost),
            widget.on("invalidated", self._on_invalidated),
        )

    @property
    def phase(self) -> InteractionPhase:
        return self._phase

    @property
    def idle_opacity(self) -> float:
        return self._idle_opacity

    @property
    def active(self) -> bool:
        animation = self._animation
        return animation is not None and animation.status is AnimationStatus.RUNNING

    @property
    def disposed(self) -> bool:
        return self._disposed

    def dispose(self, *, restore: bool = True) -> None:
        """Detach listeners, cancel the current tween and optionally restore idle opacity."""

        if self._disposed:
            return
        self._disposed = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._cancel_current()
        if restore:
            self.widget.opacity = self._idle_opacity
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._phase = InteractionPhase.IDLE

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.widget.enabled:
            self._hovered = True
            self._transition()

    def _on_pointer_leave(self, _event: Event) -> None:
        self._hovered = False
        self._pressed = False
        self._transition()

    def _on_pointer_down(self, _event: Event) -> None:
        if self.widget.enabled:
            self._pressed = True
            self._transition()

    def _on_pointer_up(self, _event: Event) -> None:
        self._pressed = False
        self._transition()

    def _on_focus_gained(self, _event: Event) -> None:
        if self.widget.enabled:
            self._focused = True
            self._transition()

    def _on_focus_lost(self, _event: Event) -> None:
        self._focused = False
        self._pressed = False
        self._transition()

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") != "enabled" or self.widget.enabled:
            return
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._transition()

    def _transition(self) -> None:
        if self._disposed:
            return
        phase = self._desired_phase()
        target = self._target_opacity(phase)
        if phase is self._phase and math.isclose(self.widget.opacity, target, abs_tol=1e-12):
            return

        previous_phase = self._phase
        self._phase = phase
        self._cancel_current()
        duration = (
            self.spec.duration
            if phase is InteractionPhase.PRESSED
            or self._priority(phase) >= self._priority(previous_phase)
            else self.spec.release_duration
        )
        animation = Tween(
            self.widget.opacity,
            target,
            duration,
            self._set_opacity,
            easing=self.easing,
        )
        self._animation = animation
        self.controller.play(animation)

    def _desired_phase(self) -> InteractionPhase:
        if not self.widget.enabled:
            return InteractionPhase.IDLE
        if self._pressed:
            return InteractionPhase.PRESSED
        if self._hovered:
            return InteractionPhase.HOVERED
        if self._focused:
            return InteractionPhase.FOCUSED
        return InteractionPhase.IDLE

    def _target_opacity(self, phase: InteractionPhase) -> float:
        if phase is InteractionPhase.PRESSED:
            return self.spec.pressed_opacity
        if phase is InteractionPhase.HOVERED:
            return self.spec.hover_opacity
        if phase is InteractionPhase.FOCUSED:
            return self.spec.focus_opacity
        return self._idle_opacity

    def _set_opacity(self, value: float) -> None:
        self.widget.opacity = value

    def _cancel_current(self) -> None:
        animation = self._animation
        if animation is not None and animation.status is AnimationStatus.RUNNING:
            animation.cancel()
        self._animation = None

    @staticmethod
    def _priority(phase: InteractionPhase) -> int:
        return {
            InteractionPhase.IDLE: 0,
            InteractionPhase.FOCUSED: 1,
            InteractionPhase.HOVERED: 2,
            InteractionPhase.PRESSED: 3,
        }[phase]


@dataclass(frozen=True, slots=True)
class MagneticInteractionSpec:
    """Spring parameters for pointer-driven visual attraction."""

    max_offset: float = 12.0
    mass: float = 1.0
    stiffness: float = 220.0
    damping: float = 22.0
    max_duration: float = 1.5

    def __post_init__(self) -> None:
        _positive("max_offset", self.max_offset)
        _positive("mass", self.mass)
        _positive("stiffness", self.stiffness)
        _non_negative("damping", self.damping)
        _positive("max_duration", self.max_duration)


class MagneticInteraction:
    """Attract a retained widget toward its pointer using a damped spring.

    Pointer coordinates are consumed in SwirUI's logical-DIP space. The target
    displacement is radial-clamped to ``max_offset`` and applied through the
    widget's visual-only offset, so layout measurement and arrangement do not
    drift while the compiled subtree, clip bounds and hit testing move together.

    Every retarget starts from the currently presented offset. Leaving or disabling
    the widget springs back to the authored idle offset, and ``dispose()`` detaches
    all listeners while optionally restoring that offset immediately.
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
        self._idle_offset = widget.visual_offset
        self._start_offset = widget.visual_offset
        self._target_offset = widget.visual_offset
        self._animation: SpringAnimation | None = None
        self._disposed = False
        self._unsubscribers = (
            widget.on("pointer_move", self._on_pointer_move),
            widget.on("pointer_leave", self._on_pointer_leave),
            widget.on("invalidated", self._on_invalidated),
        )

    @property
    def idle_offset(self) -> Point:
        return self._idle_offset

    @property
    def target_offset(self) -> Point:
        return self._target_offset

    @property
    def active(self) -> bool:
        animation = self._animation
        return animation is not None and animation.status is AnimationStatus.RUNNING

    @property
    def disposed(self) -> bool:
        return self._disposed

    def dispose(self, *, restore: bool = True) -> None:
        """Detach listeners, cancel the spring and optionally restore the idle offset."""

        if self._disposed:
            return
        self._disposed = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._cancel_current()
        self._target_offset = self._idle_offset
        if restore:
            self.widget.visual_offset = self._idle_offset

    def _on_pointer_move(self, event: Event) -> None:
        if self._disposed or not self.widget.enabled:
            return
        platform_event = event.data.get("event")
        x = getattr(platform_event, "x", None)
        y = getattr(platform_event, "y", None)
        if x is None or y is None:
            return
        pointer_x = float(x)
        pointer_y = float(y)
        if not math.isfinite(pointer_x) or not math.isfinite(pointer_y):
            return

        bounds = self.widget.bounds
        half_width = max(bounds.width * 0.5, 1.0e-9)
        half_height = max(bounds.height * 0.5, 1.0e-9)
        dx = (pointer_x - (bounds.x + half_width)) / half_width * self.spec.max_offset
        dy = (pointer_y - (bounds.y + half_height)) / half_height * self.spec.max_offset
        magnitude = math.hypot(dx, dy)
        if magnitude > self.spec.max_offset:
            scale = self.spec.max_offset / magnitude
            dx *= scale
            dy *= scale
        self._retarget(Point(self._idle_offset.x + dx, self._idle_offset.y + dy))

    def _on_pointer_leave(self, _event: Event) -> None:
        self._retarget(self._idle_offset)

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.widget.enabled:
            self._retarget(self._idle_offset)

    def _retarget(self, target: Point) -> None:
        if self._disposed:
            return
        current = self.widget.visual_offset
        if _points_close(current, target):
            self._cancel_current()
            self._target_offset = target
            if current != target:
                self.widget.visual_offset = target
            return

        self._cancel_current()
        self._start_offset = current
        self._target_offset = target
        animation = SpringAnimation(
            0.0,
            1.0,
            self._apply_progress,
            mass=self.spec.mass,
            stiffness=self.spec.stiffness,
            damping=self.spec.damping,
            max_duration=self.spec.max_duration,
        )
        self._animation = animation
        self.controller.play(animation)

    def _apply_progress(self, progress: float) -> None:
        start = self._start_offset
        target = self._target_offset
        self.widget.visual_offset = Point(
            start.x + (target.x - start.x) * progress,
            start.y + (target.y - start.y) * progress,
        )

    def _cancel_current(self) -> None:
        animation = self._animation
        if animation is not None and animation.status is AnimationStatus.RUNNING:
            animation.cancel()
        self._animation = None


def _points_close(left: Point, right: Point) -> bool:
    return math.isclose(left.x, right.x, abs_tol=1.0e-12) and math.isclose(
        left.y, right.y, abs_tol=1.0e-12
    )


def _opacity(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be finite and between 0.0 and 1.0.")
    return normalized


def _duration(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized


def _positive(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return normalized


def _non_negative(name: str, value: float) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return normalized
