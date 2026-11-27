"""Optional, bounded material feedback driven by a window's animation clock."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .animation import AnimationController, AnimationStatus, Tween, ease_out_cubic
from .core import Component, Event
from .platforms import PlatformEvent, PointerButton
from .rendering import Parallax, Point

if TYPE_CHECKING:
    from .widgets.theme_surface import ThemeSurface


class SurfaceInteraction:
    """Animate a mounted ThemeSurface's glow, shadow, border and accent sheen.

    Child controls retain layout, input and authored style. One active tween is
    retained per surface, including during rapid pointer churn. Theme changes
    apply immediately; reduced motion snaps to feedback without animation.
    Set tilt_degrees to add pointer parallax to the decorative depth layers.
    Reduced motion keeps their authored pose. Unmounting or closing disposes the binding.
    """

    def __init__(self, controller: AnimationController, surface: ThemeSurface, *,
                 tilt_degrees: float = 0) -> None:
        if controller.disposed:
            raise ValueError("Animation controller is disposed.")
        if surface.mounted_window is not controller.window:
            raise ValueError("Mount the surface in the controller's window first.")
        if surface._interaction_enabled:
            raise ValueError("Surface already has an interaction binding.")
        if not 0 <= tilt_degrees <= 35:
            raise ValueError("tilt_degrees must be between 0 and 35.")
        self._parallax = Parallax(tilt_degrees, tilt_degrees) if tilt_degrees else None
        self._pointer_tilt = (0.0, 0.0)
        self._target_tilt = (0.0, 0.0)
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
        self._publish(0, (0.0, 0.0))
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
        native = event.data.get("event")
        bounds = self.surface.bounds
        if (self._parallax and self._hovered and isinstance(native, PlatformEvent)
                and self.surface.effective_style.depth_layers and bounds.width and bounds.height):
            # Scroll views and dialogs route child input in their own coordinate space.
            ancestors = path[:path.index(self.surface) + 1]
            local = self.controller.window._pointer_events_for_path(native, ancestors)[-1]
            if local.x is not None and local.y is not None:
                plane = self._parallax.resolve(Point(local.x, local.y), bounds)
                self._pointer_tilt = (plane.rotation_x_degrees, plane.rotation_y_degrees)
        button = getattr(native, "button", None)
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
        theme = self.surface.effective_theme
        reduced = theme is not None and theme.reduced_motion
        tilt = self._pointer_tilt if self._hovered and target and not reduced else (0.0, 0.0)
        moved = tilt != self._target_tilt
        self._target_tilt = tilt
        tracking = target == self._target and not force and not immediate
        if tracking and (not moved or (self._animation is not None
                                       and self._animation.status is AnimationStatus.RUNNING)):
            return
        self._target = target
        self._cancel()
        duration = theme.motion_duration if theme else .16
        if tracking:
            duration = min(duration, .08)
        if immediate or reduced or duration == 0:
            self._publish(target, tilt)
        elif self.progress != target or self.surface._interaction_tilt != tilt:
            start = self.progress
            start_x, start_y = self.surface._interaction_tilt

            def sample(t: float) -> None:
                # Follow the latest position without restarting the entry/exit clock on every move.
                x, y = self._target_tilt
                self._publish((1 - t) * start + t * target,
                              ((1 - t) * start_x + t * x, (1 - t) * start_y + t * y))

            self._animation = Tween(0, 1, duration, sample, easing=ease_out_cubic)
            self.controller.play(self._animation)

    def _cancel(self) -> None:
        if self._animation is not None:
            self.controller.cancel(self._animation)
            self._animation = None

    def _publish(self, value: float, tilt: tuple[float, float]) -> None:
        if self.surface._interaction_progress != value or self.surface._interaction_tilt != tilt:
            self.surface._interaction_progress = value
            self.surface._interaction_tilt = tilt
            self.surface.invalidate(reason="effect")
