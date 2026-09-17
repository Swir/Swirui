"""Retained modal and notification surfaces for the SwirUI core-widget layer."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_ESCAPE = 0x1B

_MODAL_BACKDROP = Color(0.0, 0.0, 0.0, 0.62)
_MODAL_BACKGROUND = Color.from_hex("#07111C")
_MODAL_BORDER = Color.from_hex("#24506A")
_TOAST_BACKGROUND = Color.from_hex("#091723")
_TOAST_BORDER = Color.from_hex("#24506A")
_TOAST_TEXT = Color.from_hex("#F4FAFF")
_TOAST_MUTED = Color.from_hex("#8DA8B8")
_TOAST_ACCENTS = {
    "info": Color.from_hex("#62E5FF"),
    "success": Color.from_hex("#4FE29B"),
    "warning": Color.from_hex("#FFD166"),
    "error": Color.from_hex("#FF6B7A"),
}


class Modal(Widget):
    """Retained modal overlay that blocks background pointer input.

    The managed content subtree uses dialog-local logical-DIP coordinates. Scene
    compilation translates the subtree into ``dialog_bounds`` while the full
    overlay remains hit-testable so background controls cannot receive clicks.
    Escape dismisses the modal whenever focus is inside the modal subtree.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        dialog_bounds: Rect,
        content: Component | None = None,
        key: str | None = None,
        open: bool = True,
        dismiss_on_backdrop: bool = True,
        dismiss_on_escape: bool = True,
        backdrop_color: Color | None = None,
        background: Color | None = None,
        border_color: Color | None = None,
        border_width: float = 1.0,
        corner_radius: float = 18.0,
        opacity: float = 1.0,
        z_index: int = 10_000,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._validate_dialog_bounds(bounds, dialog_bounds)
        self._dialog_bounds = dialog_bounds
        self._dismiss_on_backdrop = bool(dismiss_on_backdrop)
        self._dismiss_on_escape = bool(dismiss_on_escape)
        self._backdrop_color = backdrop_color or _MODAL_BACKDROP
        self._background = background or _MODAL_BACKGROUND
        self._border_color = border_color or _MODAL_BORDER
        self._border_width = self._validate_non_negative(border_width, "border_width")
        radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._corner_radius = CornerRadius.uniform(radius)
        self._content: Component | None = None
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.DIALOG,
            accessible_name=accessible_name or "Dialog",
            accessible_description=accessible_description,
        )
        self.visible = bool(open)
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        if content is not None:
            self.set_content(content)

    @property
    def is_open(self) -> bool:
        return self.visible

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
    def dismiss_on_backdrop(self) -> bool:
        return self._dismiss_on_backdrop

    @dismiss_on_backdrop.setter
    def dismiss_on_backdrop(self, value: bool) -> None:
        self._dismiss_on_backdrop = bool(value)

    @property
    def dismiss_on_escape(self) -> bool:
        return self._dismiss_on_escape

    @dismiss_on_escape.setter
    def dismiss_on_escape(self, value: bool) -> None:
        self._dismiss_on_escape = bool(value)

    def set_content(self, content: Component) -> Modal:
        """Replace the managed dialog-local content subtree."""

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
        """Show the overlay and emit ``opened`` once when state changes."""

        if self.visible:
            return False
        self.visible = True
        self.emit("opened", reason=reason)
        return True

    def dismiss(self, *, reason: str = "programmatic") -> bool:
        """Hide the overlay and emit ``dismissed`` once when state changes."""

        if not self.visible:
            return False
        self.visible = False
        self.emit("dismissed", reason=reason)
        return True

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            hit_testable=False,
        )
        root.add(
            SceneNode(
                key=self.key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.bounds,
                fill=self._backdrop_color,
                z_index=-20,
                hit_testable=self.enabled,
            )
        )
        if self._border_width > 0.0 and self._border_color.a > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:border",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=self._dialog_bounds,
                    fill=self._border_color,
                    corner_radius=self._corner_radius,
                    z_index=-10,
                    hit_testable=False,
                )
            )
        inset = self._border_width
        surface = Rect(
            self._dialog_bounds.x + inset,
            self._dialog_bounds.y + inset,
            max(0.0, self._dialog_bounds.width - (2.0 * inset)),
            max(0.0, self._dialog_bounds.height - (2.0 * inset)),
        )
        if surface.width > 0.0 and surface.height > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:surface",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=surface,
                    fill=self._background,
                    corner_radius=CornerRadius.uniform(
                        max(0.0, self._corner_radius.top_left - inset)
                    ),
                    z_index=-5,
                    hit_testable=False,
                )
            )
        return root

    def prepare_scene_children(
        self,
        children: tuple[SceneNode, ...],
    ) -> tuple[SceneNode, ...]:
        if self._content is None:
            return ()
        child = next((node for node in children if node.key == self._content.key), None)
        if child is None:
            return ()
        self._translate_subtree(
            child,
            dx=self._dialog_bounds.x,
            dy=self._dialog_bounds.y,
        )
        wrapper = SceneNode(
            key=f"{self.key}:content",
            kind=SceneNodeKind.GROUP,
            bounds=self._dialog_bounds,
            clip_to_bounds=True,
            hit_testable=False,
        )
        wrapper.add(child)
        return (wrapper,)

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if platform_event is None or platform_event.button is not PointerButton.LEFT:
            return
        x = platform_event.x
        y = platform_event.y
        if x is None or y is None:
            return
        if self._dismiss_on_backdrop and not self._contains_point(self._dialog_bounds, x, y):
            self.dismiss(reason="backdrop")
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        if not self._dismiss_on_escape:
            return
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if platform_event is None:
            return
        if (
            platform_event.key_code == _VK_ESCAPE
            and not (platform_event.ctrl or platform_event.alt or platform_event.meta)
            and self.dismiss(reason="escape")
        ):
            event.prevent_default()

    @staticmethod
    def _contains_point(bounds: Rect, x: float, y: float) -> bool:
        return bounds.x <= x <= bounds.right and bounds.y <= y <= bounds.bottom

    @staticmethod
    def _validate_dialog_bounds(overlay: Rect, dialog: Rect) -> None:
        if dialog.width <= 0.0 or dialog.height <= 0.0:
            raise ValueError("dialog_bounds must have positive width and height.")
        if (
            dialog.x < overlay.x
            or dialog.y < overlay.y
            or dialog.right > overlay.right
            or dialog.bottom > overlay.bottom
        ):
            raise ValueError("dialog_bounds must be contained by Modal bounds.")

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized

    @classmethod
    def _translate_subtree(cls, node: SceneNode, *, dx: float, dy: float) -> None:
        bounds = node.bounds
        node.bounds = Rect(bounds.x + dx, bounds.y + dy, bounds.width, bounds.height)
        for child in node.children:
            cls._translate_subtree(child, dx=dx, dy=dy)

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None


class Dialog(Modal):
    """Semantic alias for :class:`Modal` with the same retained behavior."""


class Toast(Widget):
    """GPU-backed notification surface with deterministic lifetime control."""

    def __init__(
        self,
        message: str,
        *,
        bounds: Rect,
        title: str = "Notification",
        key: str | None = None,
        kind: str = "info",
        duration_seconds: float | None = None,
        dismiss_on_click: bool = True,
        background: Color | None = None,
        border_color: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 20_000,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._message = str(message)
        self._title = str(title)
        self._kind = self._validate_kind(kind)
        self._duration_seconds = self._validate_duration(duration_seconds)
        self._elapsed_seconds = 0.0
        self._dismiss_on_click = bool(dismiss_on_click)
        self._background = background or _TOAST_BACKGROUND
        self._border_color = border_color or _TOAST_BORDER
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=False,
            accessibility_role=AccessibilityRole.ALERT,
            accessible_name=accessible_name or self._title,
            accessible_description=accessible_description or self._message,
        )
        self.on("pointer_down", self._on_pointer_down)

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._title:
            return
        self._title = normalized
        self.accessible_name = normalized
        self.invalidate(reason="title")

    @property
    def message(self) -> str:
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._message:
            return
        self._message = normalized
        self.accessible_description = normalized
        self.invalidate(reason="message")

    @property
    def kind(self) -> str:
        return self._kind

    @kind.setter
    def kind(self, value: str) -> None:
        normalized = self._validate_kind(value)
        if normalized == self._kind:
            return
        self._kind = normalized
        self.invalidate(reason="kind")

    @property
    def duration_seconds(self) -> float | None:
        return self._duration_seconds

    @property
    def elapsed_seconds(self) -> float:
        return self._elapsed_seconds

    def reset_lifetime(self) -> None:
        self._elapsed_seconds = 0.0

    def show(self, *, reason: str = "programmatic") -> bool:
        self.reset_lifetime()
        if self.visible:
            return False
        self.visible = True
        self.emit("shown", reason=reason)
        return True

    def dismiss(self, *, reason: str = "programmatic") -> bool:
        if not self.visible:
            return False
        self.visible = False
        self.emit("dismissed", reason=reason)
        return True

    def advance(self, delta_seconds: float) -> bool:
        """Advance the deterministic lifetime clock and dismiss on timeout."""

        delta = float(delta_seconds)
        if not math.isfinite(delta) or delta < 0.0:
            raise ValueError("delta_seconds must be finite and non-negative.")
        if not self.visible or self._duration_seconds is None:
            return False
        self._elapsed_seconds += delta
        if self._elapsed_seconds < self._duration_seconds:
            return False
        return self.dismiss(reason="timeout")

    def build_scene_node(self) -> SceneNode:
        accent = _TOAST_ACCENTS[self._kind]
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=True,
            hit_testable=False,
        )
        radius = CornerRadius.uniform(14.0)
        root.add(
            SceneNode(
                key=self.key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.bounds,
                fill=self._border_color,
                corner_radius=radius,
                z_index=-20,
                hit_testable=self.enabled and self._dismiss_on_click,
            ),
            SceneNode(
                key=f"{self.key}:surface",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    self.bounds.x + 1.0,
                    self.bounds.y + 1.0,
                    max(0.0, self.bounds.width - 2.0),
                    max(0.0, self.bounds.height - 2.0),
                ),
                fill=self._background,
                corner_radius=CornerRadius.uniform(13.0),
                z_index=-15,
                hit_testable=False,
            ),
            SceneNode(
                key=f"{self.key}:accent",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    self.bounds.x + 1.0,
                    self.bounds.y + 1.0,
                    5.0,
                    self.bounds.height - 2.0,
                ),
                fill=accent,
                corner_radius=CornerRadius.uniform(2.5),
                z_index=-10,
                hit_testable=False,
            ),
        )
        if self._title:
            root.add(
                SceneNode(
                    key=f"{self.key}:title",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        self.bounds.x + 22.0,
                        self.bounds.y + 14.0,
                        max(0.0, self.bounds.width - 38.0),
                        24.0,
                    ),
                    fill=_TOAST_TEXT,
                    text=self._title,
                    font_size=15.0,
                    font_family="Segoe UI",
                    z_index=0,
                    hit_testable=False,
                )
            )
        root.add(
            SceneNode(
                key=f"{self.key}:message",
                kind=SceneNodeKind.TEXT,
                bounds=Rect(
                    self.bounds.x + 22.0,
                    self.bounds.y + (42.0 if self._title else 18.0),
                    max(0.0, self.bounds.width - 38.0),
                    max(20.0, self.bounds.height - (52.0 if self._title else 28.0)),
                ),
                fill=_TOAST_MUTED,
                text=self._message,
                font_size=13.0,
                font_family="Segoe UI",
                z_index=0,
                hit_testable=False,
            )
        )
        return root

    def _on_pointer_down(self, event: Event) -> None:
        if not self._dismiss_on_click:
            return
        platform_event = Modal._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if platform_event is None or platform_event.button is not PointerButton.LEFT:
            return
        scene_target = event.data.get("scene_target")
        if (
            isinstance(scene_target, SceneNode)
            and scene_target.key == self.key
            and self.dismiss(reason="click")
        ):
            event.prevent_default()

    @staticmethod
    def _validate_kind(value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in _TOAST_ACCENTS:
            choices = ", ".join(sorted(_TOAST_ACCENTS))
            raise ValueError(f"kind must be one of: {choices}.")
        return normalized

    @staticmethod
    def _validate_duration(value: float | None) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError("duration_seconds must be finite and greater than zero.")
        return normalized


class Notification(Toast):
    """Semantic alias for :class:`Toast` notification surfaces."""
