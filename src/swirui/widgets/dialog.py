"""Retained modal dialog surface with deterministic focus containment."""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from swirui.core import AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Point, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

if TYPE_CHECKING:
    from swirui.window import Window

_VK_RETURN = 0x0D
_VK_ESCAPE = 0x1B
_VK_TAB = 0x09

_TRANSPARENT = Color(0.0, 0.0, 0.0, 0.0)
_DEFAULT_SCRIM = Color.from_hex("#02050ACC")
_DEFAULT_PANEL = Color.from_hex("#0B1623")
_DEFAULT_PANEL_BORDER = Color.from_hex("#164D6B")
_DEFAULT_TITLE = Color.from_hex("#F4FAFF")


class DialogResult(StrEnum):
    """Reason/result reported when a :class:`Dialog` closes."""

    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    DISMISSED = "dismissed"


class Dialog(Widget):
    """Modal retained surface with scrim blocking and keyboard focus trapping.

    ``bounds`` is the full logical-DIP modal viewport. ``panel_bounds`` locates
    the dialog panel inside it. Child components use panel-local coordinates and
    are translated only in the compiled SceneGraph, preserving application-owned
    component geometry.

    A dialog starts hidden. :meth:`open` records the previously focused component,
    exposes the modal surface and moves focus to an eligible descendant (or the
    dialog itself as a fallback). While open, focus changes are guarded so Tab,
    Shift+Tab and programmatic focus cannot escape the modal subtree. Closing the
    dialog restores the prior focus when that component is still eligible.
    """

    def __init__(
        self,
        title: str,
        *,
        bounds: Rect,
        panel_bounds: Rect,
        key: str | None = None,
        scrim_color: Color | None = None,
        panel_color: Color | None = None,
        panel_border_color: Color | None = None,
        title_color: Color | None = None,
        corner_radius: float = 16.0,
        border_width: float = 1.0,
        padding: float = 20.0,
        font_size: float = 22.0,
        font_family: str = "Segoe UI",
        dismiss_on_scrim: bool = True,
        dismiss_on_escape: bool = True,
        accept_on_enter: bool = False,
        opacity: float = 1.0,
        z_index: int = 10_000,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        if panel_bounds.width <= 0.0 or panel_bounds.height <= 0.0:
            raise ValueError("panel_bounds must have positive width and height.")
        if bounds.intersection(panel_bounds) != panel_bounds:
            raise ValueError("panel_bounds must be fully contained by dialog bounds.")

        self._title = str(title)
        self._panel_bounds = panel_bounds
        self._scrim_color = scrim_color or _DEFAULT_SCRIM
        self._panel_color = panel_color or _DEFAULT_PANEL
        self._panel_border_color = panel_border_color or _DEFAULT_PANEL_BORDER
        self._title_color = title_color or _DEFAULT_TITLE
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._border_width = self._validate_non_negative(border_width, "border_width")
        self._padding = self._validate_non_negative(padding, "padding")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._dismiss_on_scrim = bool(dismiss_on_scrim)
        self._dismiss_on_escape = bool(dismiss_on_escape)
        self._accept_on_enter = bool(accept_on_enter)
        self._window: Window | None = None
        self._previous_focus: Component | None = None
        self._focus_guard_unsubscribe: Callable[[], None] | None = None
        self._scrim_pressed = False
        self._result: DialogResult | None = None
        self._auto_accessible_name = accessible_name is None

        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.DIALOG,
            accessible_name=self._title if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )
        self.visible = False
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down, capture=True)

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._title:
            return
        self._title = normalized
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="title")

    @property
    def panel_bounds(self) -> Rect:
        return self._panel_bounds

    @panel_bounds.setter
    def panel_bounds(self, value: Rect) -> None:
        if value.width <= 0.0 or value.height <= 0.0:
            raise ValueError("panel_bounds must have positive width and height.")
        if self.bounds.intersection(value) != value:
            raise ValueError("panel_bounds must be fully contained by dialog bounds.")
        if value == self._panel_bounds:
            return
        self._panel_bounds = value
        self.invalidate(reason="panel_bounds")

    @property
    def is_open(self) -> bool:
        return self.visible and self._window is not None

    @property
    def result(self) -> DialogResult | None:
        return self._result

    def open(
        self,
        window: Window,
        *,
        initial_focus: Component | None = None,
    ) -> Dialog:
        """Open the modal dialog in ``window`` and establish a focus trap."""

        if window.root is None or not self._belongs_to(window.root, self):
            raise ValueError("Dialog must belong to the target window root before opening.")
        if self._window is not None and self._window is not window:
            raise RuntimeError("Dialog is already open in another window.")
        self._validate_open_ancestry()
        if initial_focus is not None:
            if not self._belongs_to(self, initial_focus):
                raise ValueError("initial_focus must belong to the dialog subtree.")
            if not self._is_focus_candidate_for_open(initial_focus):
                raise ValueError("initial_focus must be enabled, visible and focusable.")

        if self._window is None:
            self._window = window
            self._previous_focus = window.focused_component
            self._focus_guard_unsubscribe = window.on(
                "component_focus_changed",
                self._guard_window_focus,
            )
        self._result = None
        self.visible = True
        target = self._resolve_initial_focus(initial_focus)
        window.focus_component(target)
        self.emit("opened", window=window, initial_focus=target)
        return self

    def close(self, result: DialogResult = DialogResult.DISMISSED) -> DialogResult:
        """Close the dialog, report ``result`` and restore the previous focus."""

        normalized = DialogResult(result)
        window = self._window
        if window is None:
            self._result = normalized
            self.visible = False
            return normalized

        previous_focus = self._previous_focus
        unsubscribe = self._focus_guard_unsubscribe
        self._focus_guard_unsubscribe = None
        if unsubscribe is not None:
            unsubscribe()

        self._window = None
        self._previous_focus = None
        self._scrim_pressed = False
        self._result = normalized
        self.visible = False

        if previous_focus is not None:
            try:
                window.focus_component(previous_focus)
            except ValueError:
                window.focus_component(None)
        else:
            window.focus_component(None)

        self.emit("closed", window=window, result=normalized)
        return normalized

    def accept(self) -> DialogResult:
        """Close the dialog with :attr:`DialogResult.ACCEPTED`."""

        self.emit("accepted")
        return self.close(DialogResult.ACCEPTED)

    def cancel(self) -> DialogResult:
        """Close the dialog with :attr:`DialogResult.CANCELLED`."""

        self.emit("cancelled")
        return self.close(DialogResult.CANCELLED)

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=f"{self.key}:modal-root",
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(
            SceneNode(
                key=self.key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.bounds,
                fill=self._scrim_color,
                z_index=0,
                hit_testable=True,
            )
        )

        border = self._panel_border_bounds()
        if border is not None:
            root.add(
                SceneNode(
                    key=f"{self.key}:panel-border",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=border,
                    fill=self._panel_border_color,
                    corner_radius=CornerRadius.uniform(self._corner_radius + self._border_width),
                    z_index=1,
                    hit_testable=False,
                )
            )
        root.add(
            SceneNode(
                key=self.key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.panel_bounds,
                fill=self._panel_color,
                corner_radius=CornerRadius.uniform(self._corner_radius),
                z_index=2,
                hit_testable=True,
            )
        )
        title_bounds = self._title_bounds()
        if self.title and title_bounds.width > 0.0 and title_bounds.height > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:title",
                    kind=SceneNodeKind.TEXT,
                    bounds=title_bounds,
                    fill=self._title_color,
                    text=self.title,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    z_index=3,
                    hit_testable=False,
                )
            )
        return root

    def prepare_scene_children(
        self,
        children: tuple[SceneNode, ...],
    ) -> tuple[SceneNode, ...]:
        """Translate panel-local child scenes and clip them to the modal panel."""

        prepared: list[SceneNode] = []
        for index, node in enumerate(children):
            self._translate_subtree(node, dx=self.panel_bounds.x, dy=self.panel_bounds.y)
            wrapper = SceneNode(
                key=f"{self.key}:content:{index}",
                kind=SceneNodeKind.GROUP,
                bounds=self.panel_bounds,
                fill=_TRANSPARENT,
                z_index=4 + index,
                clip_to_bounds=True,
                hit_testable=False,
            )
            wrapper.add(node)
            prepared.append(wrapper)
        return tuple(prepared)

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
        ):
            return
        outside_panel = not self.panel_bounds.contains(
            Point(platform_event.x, platform_event.y)
        )
        self._scrim_pressed = outside_panel
        if outside_panel:
            event.prevent_default()

    def _on_pointer_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if (
            platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
        ):
            self._scrim_pressed = False
            return
        outside_panel = not self.panel_bounds.contains(
            Point(platform_event.x, platform_event.y)
        )
        dismiss = self._scrim_pressed and outside_panel and self._dismiss_on_scrim
        self._scrim_pressed = False
        if outside_panel:
            event.prevent_default()
        if dismiss:
            self.close(DialogResult.DISMISSED)

    def _on_key_down(self, event: Event) -> None:
        if not self.is_open or event.default_prevented:
            return
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if platform_event is None or platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        if platform_event.key_code == _VK_TAB:
            self._focus_next(reverse=platform_event.shift)
            event.prevent_default()
        elif platform_event.key_code == _VK_ESCAPE and self._dismiss_on_escape:
            self.cancel()
            event.prevent_default()
        elif platform_event.key_code == _VK_RETURN and self._accept_on_enter:
            self.accept()
            event.prevent_default()

    def _focus_next(self, *, reverse: bool) -> Component:
        window = self._window
        if window is None:
            return self
        candidates = self._focus_candidates()
        if not candidates:
            window.focus_component(self)
            return self

        current = window.focused_component
        step = -1 if reverse else 1
        if current not in candidates:
            target = candidates[-1] if reverse else candidates[0]
        else:
            index = candidates.index(current)
            target = candidates[(index + step) % len(candidates)]
        window.focus_component(target)
        return target

    def _resolve_initial_focus(self, requested: Component | None) -> Component:
        if requested is not None:
            if not self._belongs_to(self, requested):
                raise ValueError("initial_focus must belong to the dialog subtree.")
            if not self._is_focus_candidate(requested):
                raise ValueError("initial_focus must be enabled, visible and focusable.")
            return requested
        candidates = self._focus_candidates()
        return candidates[0] if candidates else self

    def _focus_candidates(self) -> list[Component]:
        return [
            component
            for component in self.walk()
            if component is not self and self._is_focus_candidate(component)
        ]

    def _guard_window_focus(self, event: Event) -> None:
        window = self._window
        if window is None or not self.visible:
            return
        focused = event.data.get("component")
        if focused is not None and self._belongs_to(self, focused):
            return
        target = self._resolve_initial_focus(None)
        if window.focused_component is not target:
            window.focus_component(target)

    def _panel_border_bounds(self) -> Rect | None:
        width = min(
            self._border_width,
            self.panel_bounds.x - self.bounds.x,
            self.bounds.right - self.panel_bounds.right,
            self.panel_bounds.y - self.bounds.y,
            self.bounds.bottom - self.panel_bounds.bottom,
        )
        if width <= 0.0:
            return None
        return Rect(
            self.panel_bounds.x - width,
            self.panel_bounds.y - width,
            self.panel_bounds.width + (2.0 * width),
            self.panel_bounds.height + (2.0 * width),
        )

    def _title_bounds(self) -> Rect:
        line_height = min(self.panel_bounds.height, self._font_size * 1.35)
        width = max(0.0, self.panel_bounds.width - (2.0 * self._padding))
        return Rect(
            self.panel_bounds.x + self._padding,
            self.panel_bounds.y + self._padding,
            width,
            line_height,
        )

    def _validate_open_ancestry(self) -> None:
        if not self.enabled:
            raise ValueError("Dialog must be enabled before opening.")
        current = self.parent
        while current is not None:
            if not current.enabled or not current.visible:
                raise ValueError("Dialog ancestors must be enabled and visible before opening.")
            current = current.parent

    def _is_focus_candidate_for_open(self, component: Component) -> bool:
        if not component.focusable:
            return False
        current: Component | None = component
        while current is not None and current is not self:
            if not current.enabled or not current.visible:
                return False
            current = current.parent
        return current is self and self.enabled

    @staticmethod
    def _translate_subtree(node: SceneNode, *, dx: float, dy: float) -> None:
        bounds = node.bounds
        node.bounds = Rect(bounds.x + dx, bounds.y + dy, bounds.width, bounds.height)
        for child in node.children:
            Dialog._translate_subtree(child, dx=dx, dy=dy)

    @staticmethod
    def _belongs_to(root: Component, candidate: object) -> bool:
        return isinstance(candidate, Component) and any(
            component is candidate for component in root.walk()
        )

    @staticmethod
    def _is_focus_candidate(component: Component) -> bool:
        if not component.focusable:
            return False
        current: Component | None = component
        while current is not None:
            if not current.enabled or not current.visible:
                return False
            current = current.parent
        return True

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and greater than zero.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized

    @staticmethod
    def _validate_font_family(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("font_family cannot be empty.")
        return normalized
