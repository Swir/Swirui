"""Retained modal and dialog surfaces for the SwirUI core-widget layer."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from swirui.core import AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Point, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

if TYPE_CHECKING:
    from swirui.window import Window

_VK_ESCAPE = 0x1B
_VK_TAB = 0x09
_DEFAULT_SCRIM = Color(0.0, 0.02, 0.04, 0.72)
_DEFAULT_SURFACE = Color.from_hex("#07111C")
_DEFAULT_Z_INDEX = 10_000


class Modal(Widget):
    """Blocking retained overlay with a clipped dialog-local content subtree.

    ``bounds`` describes the full modal overlay in window logical DIPs while
    ``dialog_bounds`` describes the visible dialog surface in the same coordinate
    space. The managed content subtree authors its own geometry relative to the
    dialog origin and is translated only during SceneGraph compilation.

    When mounted through :class:`~swirui.widgets.WidgetRuntime`, the modal binds to
    its window, moves focus into the dialog when opened, traps Tab traversal inside
    the modal subtree, and restores the previous focus target after dismissal.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        dialog_bounds: Rect,
        content: Component | None = None,
        key: str | None = None,
        scrim_color: Color | None = None,
        background: Color | None = None,
        corner_radius: float = 18.0,
        dismiss_on_scrim: bool = True,
        dismiss_on_escape: bool = True,
        initially_open: bool = True,
        opacity: float = 1.0,
        z_index: int = _DEFAULT_Z_INDEX,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._validate_dialog_bounds(bounds, dialog_bounds)
        self._dialog_bounds = dialog_bounds
        self._scrim_color = scrim_color or _DEFAULT_SCRIM
        self._background = background or _DEFAULT_SURFACE
        self._corner_radius = CornerRadius.uniform(
            self._validate_non_negative(corner_radius, "corner_radius")
        )
        self._dismiss_on_scrim = bool(dismiss_on_scrim)
        self._dismiss_on_escape = bool(dismiss_on_escape)
        self._content: Component | None = None
        self._window: Window | None = None
        self._focus_restore: Component | None = None
        self._focus_scope_active = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=False,
            accessibility_role=AccessibilityRole.DIALOG,
            accessible_name=accessible_name or "Dialog",
            accessible_description=accessible_description,
        )
        self._visible = bool(initially_open)
        self.on("pointer_down", self._on_pointer_down, capture=True)
        self.on("key_down", self._on_key_down, capture=True)
        if content is not None:
            self.set_content(content)

    @property
    def dialog_bounds(self) -> Rect:
        return self._dialog_bounds

    @dialog_bounds.setter
    def dialog_bounds(self, value: Rect) -> None:
        self._validate_dialog_bounds(self.bounds, value)
        if value == self._dialog_bounds:
            return
        self._dialog_bounds = value
        self.invalidate(reason="dialog_bounds")

    @property
    def content(self) -> Component | None:
        return self._content

    @property
    def is_open(self) -> bool:
        return self.visible

    @property
    def dismiss_on_scrim(self) -> bool:
        return self._dismiss_on_scrim

    @dismiss_on_scrim.setter
    def dismiss_on_scrim(self, value: bool) -> None:
        self._dismiss_on_scrim = bool(value)

    @property
    def dismiss_on_escape(self) -> bool:
        return self._dismiss_on_escape

    @dismiss_on_escape.setter
    def dismiss_on_escape(self, value: bool) -> None:
        self._dismiss_on_escape = bool(value)

    def set_content(self, content: Component) -> Modal:
        """Replace the single dialog-local managed content subtree."""

        if content is self:
            raise ValueError("A Modal cannot use itself as content.")
        if content is self._content:
            return self
        if self._content is not None and self._content.parent is self:
            super().remove(self._content)
        self._content = content
        super().add(content)
        self.invalidate(reason="content")
        return self

    def add(self, *children: Component) -> Modal:
        if len(children) != 1:
            raise ValueError("Modal.add() requires exactly one content component.")
        return self.set_content(children[0])

    def remove(self, child: Component) -> Modal:
        if child is not self._content:
            raise ValueError("Component is not the managed Modal content.")
        super().remove(child)
        self._content = None
        self.invalidate(reason="content")
        return self

    def clear(self) -> None:
        if self._content is not None:
            self.remove(self._content)

    def show(self, *, reason: str = "programmatic") -> bool:
        """Open the modal and emit ``opened`` when its state changes."""

        if self.visible:
            return False
        self.visible = True
        self.emit("opened", reason=reason)
        return True

    def dismiss(self, *, reason: str = "programmatic") -> bool:
        """Close the modal and emit ``dismissed`` when its state changes."""

        if not self.visible:
            return False
        self.visible = False
        self.emit("dismissed", reason=reason)
        return True

    def bind_window(self, window: Window | None) -> None:
        """Bind runtime focus management to the mounted window."""

        if window is not self._window:
            self._deactivate_focus_scope(restore=True)
            self._window = window
            self._focus_restore = None
            self._focus_scope_active = False
        self._sync_focus_scope()

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(
            SceneNode(
                key=self.key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.bounds,
                fill=self._scrim_color,
                z_index=-100,
                hit_testable=self.enabled,
            ),
            SceneNode(
                key=f"{self.key}:surface",
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.dialog_bounds,
                fill=self._background,
                corner_radius=self._corner_radius,
                z_index=-50,
                hit_testable=False,
            ),
        )
        return root

    def prepare_scene_children(
        self,
        children: tuple[SceneNode, ...],
    ) -> tuple[SceneNode, ...]:
        """Translate dialog-local content and clip it to the dialog surface."""

        content = self._content
        if content is None:
            return ()
        child = next((node for node in children if node.key == content.key), None)
        if child is None:
            return ()
        self._translate_subtree(
            child,
            dx=self.dialog_bounds.x,
            dy=self.dialog_bounds.y,
        )
        wrapper = SceneNode(
            key=f"{self.key}:content",
            kind=SceneNodeKind.GROUP,
            bounds=self.dialog_bounds,
            z_index=0,
            clip_to_bounds=True,
            hit_testable=False,
        )
        wrapper.add(child)
        return (wrapper,)

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or not self.visible
            or not self._dismiss_on_scrim
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
        ):
            return
        if self.dialog_bounds.contains(Point(platform_event.x, platform_event.y)):
            return
        if self.dismiss(reason="scrim"):
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        if not self.enabled or not self.visible:
            return
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if platform_event is None:
            return

        if (
            platform_event.key_code == _VK_ESCAPE
            and self._dismiss_on_escape
            and not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
        ):
            if self.dismiss(reason="escape"):
                event.prevent_default()
            return

        if (
            platform_event.key_code != _VK_TAB
            or platform_event.ctrl
            or platform_event.alt
            or platform_event.meta
        ):
            return
        candidates = self._focus_candidates()
        window = self._window
        if window is None or not candidates:
            event.prevent_default()
            return
        current = window.focused_component
        step = -1 if platform_event.shift else 1
        if current not in candidates:
            target = candidates[-1] if platform_event.shift else candidates[0]
        else:
            index = candidates.index(current)
            target = candidates[(index + step) % len(candidates)]
        window.focus_component(target)
        event.prevent_default()

    def _sync_focus_scope(self) -> None:
        window = self._window
        should_be_active = window is not None and self.visible and self.enabled
        if should_be_active and not self._focus_scope_active:
            current = window.focused_component
            if current is not None and not self._contains_component(current):
                self._focus_restore = current
            self._focus_scope_active = True
            candidates = self._focus_candidates()
            if candidates:
                window.focus_component(candidates[0])
            elif current is not None and self._contains_component(current):
                self._focus_restore = None
        elif not should_be_active and self._focus_scope_active:
            self._deactivate_focus_scope(restore=True)

    def _deactivate_focus_scope(self, *, restore: bool) -> None:
        if not self._focus_scope_active:
            return
        window = self._window
        restore_target = self._focus_restore
        self._focus_scope_active = False
        self._focus_restore = None
        if window is None:
            return
        if restore and restore_target is not None:
            try:
                window.focus_component(restore_target)
                return
            except ValueError:
                pass
        if window.focused_component is not None and self._contains_component(
            window.focused_component
        ):
            window.focus_component(None)

    def _focus_candidates(self) -> list[Component]:
        return [
            component
            for component in self.walk(include_self=False)
            if component.focusable and self._component_path_available(component)
        ]

    def _component_path_available(self, component: Component) -> bool:
        current: Component | None = component
        while current is not None:
            if not current.enabled or not current.visible:
                return False
            if current is self:
                return True
            current = current.parent
        return False

    def _contains_component(self, component: Component) -> bool:
        return component is self or any(item is component for item in self.walk())

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if not isinstance(platform_event, PlatformEvent) or platform_event.kind is not kind:
            return None
        return platform_event

    @staticmethod
    def _translate_subtree(node: SceneNode, *, dx: float, dy: float) -> None:
        node.bounds = Rect(
            node.bounds.x + dx,
            node.bounds.y + dy,
            node.bounds.width,
            node.bounds.height,
        )
        for child in node.children:
            Modal._translate_subtree(child, dx=dx, dy=dy)

    @staticmethod
    def _validate_dialog_bounds(overlay: Rect, dialog: Rect) -> None:
        if dialog.width <= 0.0 or dialog.height <= 0.0:
            raise ValueError("dialog_bounds must have positive dimensions.")
        if (
            dialog.x < overlay.x
            or dialog.y < overlay.y
            or dialog.right > overlay.right
            or dialog.bottom > overlay.bottom
        ):
            raise ValueError("dialog_bounds must be fully contained by bounds.")

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized


class Dialog(Modal):
    """Semantic name for a modal dialog surface."""
