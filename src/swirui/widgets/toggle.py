"""Retained checkbox, radio-button and switch widgets."""

from __future__ import annotations

from typing import Any, TypeGuard

from swirui.core import AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_ACTIVATION_KEYS = {0x0D, 0x20, 0xFF0D, 0xFF8D}
_DEFAULT_TRACK = Color.from_hex("#253746")
_DEFAULT_TRACK_CHECKED = Color.from_hex("#087FCE")
_DEFAULT_TRACK_HOVER = Color.from_hex("#315065")
_DEFAULT_DISABLED = Color.from_hex("#33424C")
_DEFAULT_FOREGROUND = Color.from_hex("#F4FAFF")
_DEFAULT_ACCENT = Color.from_hex("#62E5FF")
_DEFAULT_THUMB = Color.from_hex("#F4FAFF")
_TRANSPARENT = Color(0.0, 0.0, 0.0, 0.0)


class _ToggleBase(Widget):
    """Shared routed-input behavior for boolean selection widgets."""

    def __init__(
        self,
        *,
        bounds: Rect,
        checked: bool,
        role: AccessibilityRole,
        accessible_name: str,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_description: str | None = None,
    ) -> None:
        self._checked = bool(checked)
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
            accessible_name=accessible_name,
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
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self._set_checked(bool(value), reason="checked")

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
        self._set_checked(not self._checked, reason="toggle")

    def _activate(self, input_event: Event) -> None:
        if not self.enabled:
            return
        self.toggle()
        self.emit("click", checked=self._checked, input_event=input_event)

    def _set_checked(self, checked: bool, *, reason: str) -> None:
        normalized = bool(checked)
        if normalized == self._checked:
            return
        old_checked = self._checked
        self._checked = normalized
        self.invalidate(reason=reason)
        self.emit(
            "checked_changed",
            old_checked=old_checked,
            checked=normalized,
            reason=reason,
        )

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
        self._set_interaction_state(
            hovered=False,
            pressed=False,
            reason="pointer_leave",
        )

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
            self._activate(event)

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None:
            return
        if platform_event.key_code not in _ACTIVATION_KEYS:
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        self._set_interaction_state(pressed=True, reason="key_down")
        event.prevent_default()

    def _on_key_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_UP)
        if platform_event is None or platform_event.key_code not in _ACTIVATION_KEYS:
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        activate = self.enabled and self._pressed
        self._set_interaction_state(pressed=False, reason="key_up")
        event.prevent_default()
        if activate:
            self._activate(event)

    def _on_focus_gained(self, _event: Event) -> None:
        self._set_interaction_state(focused=True, reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        self._set_interaction_state(
            focused=False,
            pressed=False,
            reason="focus_lost",
        )

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


class Checkbox(_ToggleBase):
    """Focusable checkbox with retained GPU box, mark and label visuals."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        checked: bool = False,
        key: str | None = None,
        foreground: Color | None = None,
        accent: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._accent = accent or _DEFAULT_ACCENT
        super().__init__(
            bounds=bounds,
            checked=checked,
            role=AccessibilityRole.CHECKBOX,
            accessible_name=accessible_name or self._text or "Checkbox",
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessible_description=accessible_description,
        )

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._text:
            return
        self._text = normalized
        self.invalidate(reason="text")

    def build_scene_node(self) -> SceneNode:
        box_size = min(22.0, self.bounds.height)
        box_y = self.bounds.y + ((self.bounds.height - box_size) / 2.0)
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            hit_testable=self.enabled,
        )
        root.add(
            SceneNode(
                key=f"{self.key}:box",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(self.bounds.x, box_y, box_size, box_size),
                fill=self._box_color(),
                corner_radius=CornerRadius.uniform(5.0),
                hit_testable=False,
            )
        )
        if self.checked:
            root.add(
                SceneNode(
                    key=f"{self.key}:mark",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        self.bounds.x + 3.0,
                        box_y,
                        box_size - 6.0,
                        box_size,
                    ),
                    fill=_DEFAULT_FOREGROUND,
                    text="✓",
                    font_size=16.0,
                    font_family="Segoe UI Symbol",
                    hit_testable=False,
                    z_index=1,
                )
            )
        if self._text:
            root.add(self._label_node(box_size))
        return root

    def _label_node(self, indicator_size: float) -> SceneNode:
        return SceneNode(
            key=f"{self.key}:label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(
                self.bounds.x + indicator_size + 9.0,
                self.bounds.y,
                max(0.0, self.bounds.width - indicator_size - 9.0),
                self.bounds.height,
            ),
            fill=self._foreground,
            text=self._text,
            font_size=16.0,
            font_family="Segoe UI",
            hit_testable=False,
        )

    def _box_color(self) -> Color:
        if not self.enabled:
            return _DEFAULT_DISABLED
        if self.checked:
            return self._accent
        if self.hovered or self.focused:
            return _DEFAULT_TRACK_HOVER
        return _DEFAULT_TRACK


class RadioButton(Checkbox):
    """Mutually-exclusive retained selector scoped by a logical group name."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        group: str = "default",
        checked: bool = False,
        **kwargs: Any,
    ) -> None:
        normalized_group = str(group).strip()
        if not normalized_group:
            raise ValueError("group cannot be empty.")
        self.group = normalized_group
        super().__init__(text, bounds=bounds, checked=checked, **kwargs)
        self.accessibility_role = AccessibilityRole.RADIO

    def toggle(self) -> None:
        if not self.checked:
            self._set_checked(True, reason="radio_select")

    def _set_checked(self, checked: bool, *, reason: str) -> None:
        normalized = bool(checked)
        if normalized and not self._checked:
            root = self._tree_root()
            for component in root.walk():
                if self._is_checked_peer(component):
                    component._set_checked(False, reason="radio_group")
        super()._set_checked(normalized, reason=reason)

    def _is_checked_peer(self, component: Component) -> TypeGuard[RadioButton]:
        return (
            isinstance(component, RadioButton)
            and component is not self
            and component.group == self.group
            and component.checked
        )

    def build_scene_node(self) -> SceneNode:
        diameter = min(22.0, self.bounds.height)
        ring_y = self.bounds.y + ((self.bounds.height - diameter) / 2.0)
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            hit_testable=self.enabled,
        )
        root.add(
            SceneNode(
                key=f"{self.key}:ring",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(self.bounds.x, ring_y, diameter, diameter),
                fill=self._box_color(),
                corner_radius=CornerRadius.uniform(diameter / 2.0),
                hit_testable=False,
            )
        )
        if self.checked:
            inner = diameter * 0.42
            inset = (diameter - inner) / 2.0
            root.add(
                SceneNode(
                    key=f"{self.key}:dot",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(
                        self.bounds.x + inset,
                        ring_y + inset,
                        inner,
                        inner,
                    ),
                    fill=_DEFAULT_FOREGROUND,
                    corner_radius=CornerRadius.uniform(inner / 2.0),
                    hit_testable=False,
                    z_index=1,
                )
            )
        if self.text:
            root.add(self._label_node(diameter))
        return root

    def _tree_root(self) -> Component:
        current: Component = self
        while current.parent is not None:
            current = current.parent
        return current


class Switch(_ToggleBase):
    """Focusable on/off switch rendered by retained rounded rectangles."""

    def __init__(
        self,
        *,
        bounds: Rect,
        checked: bool = False,
        key: str | None = None,
        track: Color | None = None,
        checked_track: Color | None = None,
        thumb: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Switch",
        accessible_description: str | None = None,
    ) -> None:
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("Switch bounds must have positive dimensions.")
        self._track = track or _DEFAULT_TRACK
        self._checked_track = checked_track or _DEFAULT_TRACK_CHECKED
        self._thumb = thumb or _DEFAULT_THUMB
        super().__init__(
            bounds=bounds,
            checked=checked,
            role=AccessibilityRole.SWITCH,
            accessible_name=accessible_name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessible_description=accessible_description,
        )

    def build_scene_node(self) -> SceneNode:
        radius = self.bounds.height / 2.0
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._track_color(),
            corner_radius=CornerRadius.uniform(radius),
            hit_testable=self.enabled,
        )
        inset = max(2.0, self.bounds.height * 0.10)
        thumb_size = max(1.0, self.bounds.height - (2.0 * inset))
        thumb_x = self.bounds.x + inset
        if self.checked:
            thumb_x = self.bounds.x + self.bounds.width - inset - thumb_size
        root.add(
            SceneNode(
                key=f"{self.key}:thumb",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    thumb_x,
                    self.bounds.y + inset,
                    thumb_size,
                    thumb_size,
                ),
                fill=self._thumb,
                corner_radius=CornerRadius.uniform(thumb_size / 2.0),
                hit_testable=False,
                z_index=1,
            )
        )
        return root

    def _track_color(self) -> Color:
        if not self.enabled:
            return _DEFAULT_DISABLED
        if self.checked:
            return self._checked_track
        if self.hovered or self.focused:
            return _DEFAULT_TRACK_HOVER
        return self._track
