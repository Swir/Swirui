"""Optional, bounded material feedback driven by a window's animation clock."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .animation import AnimationController, Tween, ease_out_cubic
from .core import Component, Event
from .platforms import PointerButton

if TYPE_CHECKING:
    from .widgets.theme_surface import ThemeSurface


class SurfaceInteraction:
    """Animate a mounted ThemeSurface's glow, shadow, border and accent sheen.

    Child controls retain layout, input and authored style. One active tween is
    retained per surface, including during rapid pointer churn. Theme changes
    apply immediately; reduced motion snaps to feedback without animation.
    Unmounting the surface or closing its window disposes the binding.
    """

    def __init__(self, controller: AnimationController, surface: ThemeSurface) -> None:
        if controller.disposed:
            raise ValueError("Animation controller is disposed.")
        if surface.mounted_window is not controller.window:
            raise ValueError("Mount the surface in the controller's window first.")
        if surface._interaction_enabled:
            raise ValueError("Surface already has an interaction binding.")
        self.controller = controller
        self.surface = surface
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._target = 0.0
        self._animation: Tween | None = None
        self._disposed = False
        surface._interaction_enabled = True
        window = controller.window
        self._unsubscribers = (
            window.on("pointer_move", self._pointer),
            window.on("pointer_down", self._pointer),
            window.on("pointer_up", self._pointer),
            window.on("component_focus_changed", self._focus),
            window.on("focus_changed", self._window_focus),
            window.on("closed", self._detach),
            surface.on("unmounted", self._detach),
            surface.on("theme_changed", self._theme),
            surface.on("invalidated", self._invalidated),
        )
        surface.invalidate(reason="effect")
        self._focus(Event("component_focus_changed", window))

    @property
    def progress(self) -> float:
        return self.surface._interaction_progress

    @property
    def disposed(self) -> bool:
        return self._disposed

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._cancel()
        self.surface._interaction_enabled = False
        self._publish(0)
        self.surface.invalidate(reason="effect")

    def _detach(self, _event: Event) -> None:
        self.dispose()

    def _available(self) -> bool:
        node: Component | None = self.surface
        while node is not None:
            if not node.enabled or not node.visible:
                return False
            node = node.parent
        return self.surface.mounted_window is self.controller.window

    def _pointer(self, event: Event) -> None:
        path = event.data.get("hit_component_path", ())
        self._hovered = self._available() and self.surface in path
        button = getattr(event.data.get("event"), "button", None)
        if event.type == "pointer_down" and button == PointerButton.LEFT:
            self._pressed = self._hovered
        elif event.type == "pointer_up" and button == PointerButton.LEFT:
            self._pressed = False
        self._transition()

    def _focus(self, _event: Event) -> None:
        node = self.controller.window.focused_component
        self._focused = False
        while node is not None:
            if node is self.surface:
                self._focused = True
                break
            node = node.parent
        self._transition()

    def _window_focus(self, event: Event) -> None:
        if not event.data.get("focused"):
            self._hovered = self._pressed = self._focused = False
            self._transition(immediate=True)
        else:
            self._focus(event)

    def _theme(self, _event: Event) -> None:
        self._transition(force=True)

    def _invalidated(self, event: Event) -> None:
        if event.data.get("reason") in {"enabled", "visible"} and not self._available():
            self._hovered = self._pressed = self._focused = False
            self._transition(immediate=True)

    def _transition(self, *, immediate: bool = False, force: bool = False) -> None:
        if self._disposed:
            return
        target = (.35 if self._pressed else 1.0) if self._hovered else (
            .65 if self._focused else 0.0
        )
        if not self._available():
            target = 0.0
        if target == self._target and not force and not immediate:
            return
        self._target = target
        self._cancel()
        theme = self.surface.effective_theme
        duration = theme.motion_duration if theme else .16
        if immediate or (theme is not None and theme.reduced_motion) or duration == 0:
            self._publish(target)
        elif self.progress != target:
            self._animation = Tween(self.progress, target, duration, self._publish,
                                    easing=ease_out_cubic)
            self.controller.play(self._animation)

    def _cancel(self) -> None:
        if self._animation is not None:
            self.controller.cancel(self._animation)
            self._animation = None

    def _publish(self, value: float) -> None:
        if self.surface._interaction_progress != value:
            self.surface._interaction_progress = value
            self.surface.invalidate(reason="effect")
