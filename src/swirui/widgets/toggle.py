"""Retained checkbox, radio button, and switch widgets."""

from __future__ import annotations

from typing import Any

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_TRANSPARENT = Color(0.0, 0.0, 0.0, 0.0)
_SURFACE = Color.from_hex("#172632")
_SURFACE_HOVER = Color.from_hex("#20394A")
_SURFACE_FOCUS = Color.from_hex("#27465A")
_SURFACE_DISABLED = Color.from_hex("#263038")
_ACCENT = Color.from_hex("#0A98F0")
_ACCENT_HOVER = Color.from_hex("#28B2FF")
_ACCENT_PRESSED = Color.from_hex("#087FCE")
_FOREGROUND = Color.from_hex("#F4FAFF")
_FOREGROUND_DISABLED = Color.from_hex("#758792")
_MARK = Color.from_hex("#F4FAFF")


class _ToggleControl(Widget):
    """Shared retained interaction and checked-state model."""

    indicator_width = 22.0
    indicator_height = 22.0
    indicator_gap = 10.0

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        role: AccessibilityRole,
        checked: bool = False,
        key: str | None = None,
        font_size: float = 16.0,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._checked = bool(checked)
        self._font_size = float(font_size)
        if self._font_size <= 0.0:
            raise ValueError("font_size must be greater than zero.")
        self._font_family = font_family.strip()
        if not self._font_family:
            raise ValueError("font_family cannot be empty.")
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
            accessibility_role=role,
            accessible_name=self._text if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )
        self.accessible_checked = self._checked
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
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self._set_checked(bool(value), input_event=None)

    @property
    def hovered(self) -> bool:
        return self._hovered

    @property
    def pressed(self) -> bool:
        return self._pressed

    @property
    def focused(self) -> bool:
        return self._focused

    def toggle(self) -> None:
        self._activate(input_event=None)

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            hit_testable=self.enabled,
        )
        indicator = self._indicator_bounds()
        if indicator.width > 0.0 and indicator.height > 0.0:
            self._build_indicator(root, indicator)
        label = self._label_bounds(indicator)
        if self._text and label.width > 0.0 and label.height > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:label",
                    kind=SceneNodeKind.TEXT,
                    bounds=label,
                    z_index=2,
                    fill=_FOREGROUND if self.enabled else _FOREGROUND_DISABLED,
                    text=self._text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        return root

    def _indicator_bounds(self) -> Rect:
        width = max(0.0, min(self.indicator_width, self.bounds.width))
        height = max(0.0, min(self.indicator_height, self.bounds.height))
        y = self.bounds.y + max(0.0, (self.bounds.height - height) * 0.5)
        return Rect(self.bounds.x, y, width, height)

    def _label_bounds(self, indicator: Rect) -> Rect:
        x = indicator.right + (self.indicator_gap if indicator.width > 0.0 else 0.0)
        width = max(0.0, self.bounds.right - x)
        height = min(self.bounds.height, self._font_size * 1.25)
        y = self.bounds.y + max(0.0, (self.bounds.height - height) * 0.5)
        return Rect(x, y, width, height)

    def _build_indicator(self, root: SceneNode, bounds: Rect) -> None:
        raise NotImplementedError

    def _surface_color(self) -> Color:
        if not self.enabled:
            return _SURFACE_DISABLED
        if self._checked:
            if self._pressed:
                return _ACCENT_PRESSED
            if self._hovered:
                return _ACCENT_HOVER
            return _ACCENT
        if self._pressed or self._focused:
            return _SURFACE_FOCUS
        if self._hovered:
            return _SURFACE_HOVER
        return _SURFACE

    def _activate(self, *, input_event: Event | None) -> None:
        self._set_checked(not self._checked, input_event=input_event)

    def _set_checked(self, value: bool, *, input_event: Event | None) -> None:
        if value == self._checked:
            return
        old_checked = self._checked
        self._checked = value
        self.accessible_checked = value
        self.invalidate(reason="checked")
        self.emit(
            "changed",
            old_checked=old_checked,
            checked=value,
            input_event=input_event,
        )

    def _set_interaction(
        self,
        *,
        hovered: bool | None = None,
        pressed: bool | None = None,
        focused: bool | None = None,
        reason: str,
    ) -> None:
        old = (self._hovered, self._pressed, self._focused)
        if hovered is not None:
            self._hovered = hovered
        if pressed is not None:
            self._pressed = pressed
        if focused is not None:
            self._focused = focused
        if old != (self._hovered, self._pressed, self._focused):
            self.invalidate(reason=reason)

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.enabled:
            self._set_interaction(hovered=True, reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        self._set_interaction(hovered=False, pressed=False, reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if self.enabled and native is not None and native.button is PointerButton.LEFT:
            self._set_interaction(pressed=True, reason="pointer_down")

    def _on_pointer_up(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if native is None or native.button is not PointerButton.LEFT:
            return
        activate = self.enabled and self._pressed
        self._set_interaction(pressed=False, reason="pointer_up")
        if activate:
            self._activate(input_event=event)

    def _on_key_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self._activation_key(native) or not self.enabled:
            return
        self._set_interaction(pressed=True, reason="key_down")
        event.prevent_default()

    def _on_key_up(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_UP)
        if not self._activation_key(native):
            return
        activate = self.enabled and self._pressed
        self._set_interaction(pressed=False, reason="key_up")
        event.prevent_default()
        if activate:
            self._activate(input_event=event)

    def _on_focus_gained(self, _event: Event) -> None:
        self._set_interaction(focused=True, reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        self._set_interaction(focused=False, pressed=False, reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._hovered = False
            self._pressed = False

    @staticmethod
    def _activation_key(event: PlatformEvent | None) -> bool:
        return bool(
            event is not None
            and event.key_code in (_VK_RETURN, _VK_SPACE)
            and not event.ctrl
            and not event.alt
            and not event.meta
        )

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        native = event.data.get("event")
        if isinstance(native, PlatformEvent) and native.kind is kind:
            return native
        return None


class Checkbox(_ToggleControl):
    """Boolean checkbox with retained GPU visuals and checked semantics."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        checked: bool = False,
        key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text,
            bounds=bounds,
            checked=checked,
            key=key,
            role=AccessibilityRole.CHECKBOX,
            **kwargs,
        )

    def _build_indicator(self, root: SceneNode, bounds: Rect) -> None:
        root.add(
            SceneNode(
                key=f"{self.key}:indicator",
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                z_index=1,
                fill=self._surface_color(),
                corner_radius=CornerRadius.uniform(min(5.0, bounds.width * 0.24)),
                hit_testable=False,
            )
        )
        if self.checked:
            root.add(
                SceneNode(
                    key=f"{self.key}:mark",
                    kind=SceneNodeKind.TEXT,
                    bounds=bounds,
                    z_index=2,
                    fill=_MARK,
                    text="✓",
                    font_size=max(10.0, bounds.height * 0.72),
                    font_family="Segoe UI Symbol",
                    hit_testable=False,
                )
            )


class RadioButton(_ToggleControl):
    """Mutually exclusive radio control scoped by parent and group name."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        checked: bool = False,
        group: str = "default",
        key: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._group = group.strip()
        if not self._group:
            raise ValueError("group cannot be empty.")
        super().__init__(
            text,
            bounds=bounds,
            checked=checked,
            key=key,
            role=AccessibilityRole.RADIO,
            **kwargs,
        )

    @property
    def group(self) -> str:
        return self._group

    def _activate(self, *, input_event: Event | None) -> None:
        if not self.checked:
            self._set_checked(True, input_event=input_event)

    def _set_checked(self, value: bool, *, input_event: Event | None) -> None:
        if value and self.parent is not None:
            for sibling in tuple(self.parent.children):
                if (
                    sibling is not self
                    and isinstance(sibling, RadioButton)
                    and sibling.group == self.group
                    and sibling.checked
                ):
                    sibling._set_checked(False, input_event=input_event)
        super()._set_checked(value, input_event=input_event)

    def _build_indicator(self, root: SceneNode, bounds: Rect) -> None:
        radius = min(bounds.width, bounds.height) * 0.5
        root.add(
            SceneNode(
                key=f"{self.key}:indicator",
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                z_index=1,
                fill=self._surface_color(),
                corner_radius=CornerRadius.uniform(radius),
                hit_testable=False,
            )
        )
        if not self.checked:
            return
        diameter = min(bounds.width, bounds.height) * 0.42
        x = bounds.x + ((bounds.width - diameter) * 0.5)
        y = bounds.y + ((bounds.height - diameter) * 0.5)
        root.add(
            SceneNode(
                key=f"{self.key}:mark",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(x, y, diameter, diameter),
                z_index=2,
                fill=_MARK,
                corner_radius=CornerRadius.uniform(diameter * 0.5),
                hit_testable=False,
            )
        )


class Switch(_ToggleControl):
    """Focusable on/off switch with retained track and knob geometry."""

    indicator_width = 40.0
    indicator_height = 22.0
    indicator_gap = 12.0

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        checked: bool = False,
        key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text,
            bounds=bounds,
            checked=checked,
            key=key,
            role=AccessibilityRole.SWITCH,
            **kwargs,
        )

    def _build_indicator(self, root: SceneNode, bounds: Rect) -> None:
        root.add(
            SceneNode(
                key=f"{self.key}:track",
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                z_index=1,
                fill=self._surface_color(),
                corner_radius=CornerRadius.uniform(bounds.height * 0.5),
                hit_testable=False,
            )
        )
        knob_size = max(0.0, min(bounds.height - 6.0, bounds.width - 6.0))
        if knob_size <= 0.0:
            return
        left = bounds.x + 3.0
        right = bounds.right - 3.0 - knob_size
        x = right if self.checked else left
        y = bounds.y + ((bounds.height - knob_size) * 0.5)
        root.add(
            SceneNode(
                key=f"{self.key}:knob",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(x, y, knob_size, knob_size),
                z_index=2,
                fill=_MARK,
                corner_radius=CornerRadius.uniform(knob_size * 0.5),
                hit_testable=False,
            )
        )
