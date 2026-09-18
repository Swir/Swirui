"""Retained button widgets with routed pointer and keyboard interaction."""

from __future__ import annotations

import math
from typing import Any

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .measurement import measure_text_block

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_DEFAULT_BACKGROUND = Color.from_hex("#087FCE")
_DEFAULT_HOVER_BACKGROUND = Color.from_hex("#0A98F0")
_DEFAULT_PRESSED_BACKGROUND = Color.from_hex("#0567A8")
_DEFAULT_FOCUSED_BACKGROUND = Color.from_hex("#149FEF")
_DEFAULT_DISABLED_BACKGROUND = Color.from_hex("#33424C")
_DEFAULT_FOREGROUND = Color.from_hex("#F4FAFF")


class Button(Widget):
    """Focusable button built on retained rectangles and native shaped text."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        key: str | None = None,
        background: Color | None = None,
        hover_background: Color | None = None,
        pressed_background: Color | None = None,
        focused_background: Color | None = None,
        disabled_background: Color | None = None,
        foreground: Color | None = None,
        corner_radius: float = 8.0,
        font_size: float = 16.0,
        font_family: str = "Segoe UI",
        padding: float = 12.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._background = background or _DEFAULT_BACKGROUND
        self._hover_background = hover_background or _DEFAULT_HOVER_BACKGROUND
        self._pressed_background = pressed_background or _DEFAULT_PRESSED_BACKGROUND
        self._focused_background = focused_background or _DEFAULT_FOCUSED_BACKGROUND
        self._disabled_background = disabled_background or _DEFAULT_DISABLED_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._auto_accessible_name = accessible_name is None
        self._hovered = False
        self._pressed = False
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.BUTTON,
            accessible_name=self._text if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_enter", self._on_pointer_enter)
        self.on("pointer_leave", self._on_pointer_leave)
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down)
        self.on("key_up", self._on_key_up)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._text:
            return
        self._text = normalized
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="text")

    @property
    def hovered(self) -> bool:
        return self._hovered

    @property
    def pressed(self) -> bool:
        return self._pressed

    @property
    def focused(self) -> bool:
        return self._focused

    def intrinsic_size(self, available: Size | None = None) -> Size:
        """Measure the button label and retain explicit authored minimum geometry."""

        _ = available
        content = measure_text_block(
            self.text,
            font_size=self._font_size,
            wrap=False,
        )
        return Size(
            max(self.preferred_size.width, content.width + (2.0 * self._padding)),
            max(self.preferred_size.height, content.height),
        )

    def build_scene_node(self) -> SceneNode:
        node = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._current_background(),
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        content_bounds = self._content_bounds()
        if self.text and content_bounds.width > 0.0 and content_bounds.height > 0.0:
            node.add(
                SceneNode(
                    key=f"{self.key}:content",
                    kind=SceneNodeKind.TEXT,
                    bounds=content_bounds,
                    fill=self._foreground,
                    text=self.text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        return node

    def _content_bounds(self) -> Rect:
        width = max(0.0, self.bounds.width - (2.0 * self._padding))
        line_height = self._font_size * 1.25
        content_height = min(self.bounds.height, line_height)
        y = self.bounds.y + max(0.0, (self.bounds.height - content_height) * 0.5)
        return Rect(self.bounds.x + self._padding, y, width, content_height)

    def _current_background(self) -> Color:
        if not self.enabled:
            return self._disabled_background
        if self._pressed:
            return self._pressed_background
        if self._hovered:
            return self._hover_background
        if self._focused:
            return self._focused_background
        return self._background

    def _set_interaction_state(
        self,
        *,
        hovered: bool | None = None,
        pressed: bool | None = None,
        focused: bool | None = None,
        reason: str,
    ) -> None:
        changed = False
        if hovered is not None and hovered != self._hovered:
            self._hovered = hovered
            changed = True
        if pressed is not None and pressed != self._pressed:
            self._pressed = pressed
            changed = True
        if focused is not None and focused != self._focused:
            self._focused = focused
            changed = True
        if changed:
            self.invalidate(reason=reason)

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.enabled:
            self._set_interaction_state(hovered=True, reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        self._set_interaction_state(hovered=False, pressed=False, reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
        ):
            return
        self._set_interaction_state(pressed=True, reason="pointer_down")

    def _on_pointer_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if platform_event is None or platform_event.button is not PointerButton.LEFT:
            return
        activate = self.enabled and self._pressed
        self._set_interaction_state(pressed=False, reason="pointer_up")
        if activate:
            self.emit("click", input_event=event)

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None:
            return
        if platform_event.key_code not in (_VK_RETURN, _VK_SPACE):
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        self._set_interaction_state(pressed=True, reason="key_down")
        event.prevent_default()

    def _on_key_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_UP)
        if platform_event is None or platform_event.key_code not in (_VK_RETURN, _VK_SPACE):
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        activate = self.enabled and self._pressed
        self._set_interaction_state(pressed=False, reason="key_up")
        event.prevent_default()
        if activate:
            self.emit("click", input_event=event)

    def _on_focus_gained(self, _event: Event) -> None:
        self._set_interaction_state(focused=True, reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        self._set_interaction_state(focused=False, pressed=False, reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._hovered = False
            self._pressed = False

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


class IconButton(Button):
    """Compact button for a Unicode icon/glyph with an explicit accessible name."""

    def __init__(
        self,
        icon: str,
        *,
        bounds: Rect,
        accessible_name: str,
        key: str | None = None,
        font_size: float = 18.0,
        font_family: str = "Segoe UI Symbol",
        **kwargs: Any,
    ) -> None:
        normalized_icon = icon.strip()
        if not normalized_icon:
            raise ValueError("icon cannot be empty.")
        normalized_name = accessible_name.strip()
        if not normalized_name:
            raise ValueError("IconButton requires a non-empty accessible_name.")
        super().__init__(
            normalized_icon,
            bounds=bounds,
            key=key,
            accessible_name=normalized_name,
            font_size=font_size,
            font_family=font_family,
            padding=0.0,
            **kwargs,
        )

    @property
    def icon(self) -> str:
        return self.text

    @icon.setter
    def icon(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            raise ValueError("icon cannot be empty.")
        self.text = normalized
