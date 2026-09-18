"""Event-driven hover, press and focus animation helpers for retained widgets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .animation import AnimationController, AnimationStatus, Easing, Tween, ease_out_cubic
from .core import Event

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
