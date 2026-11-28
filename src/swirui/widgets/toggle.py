"""Retained checkbox, radio button, and switch widgets."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from swirui.animation import AnimationController, Tween, ease_in_out_cubic
from swirui.core import AccessibilityRole, Event, state_transaction
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Path2D, Point, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import DEFAULT_THEME, Theme

from .base import Widget

if TYPE_CHECKING:
    from swirui.window import Window

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
        theme: Theme | None = None,
        checked: bool = False,
        key: str | None = None,
        font_size: float = 16.0,
        font_family: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._surface = theme.surface_color("raised") if theme else _SURFACE
        self._surface_hover = theme.surface_color("hover") if theme else _SURFACE_HOVER
        self._surface_focus = theme.surface_color("pressed") if theme else _SURFACE_FOCUS
        self._surface_disabled = theme.surface_color("disabled") if theme else _SURFACE_DISABLED
        self._accent = theme.surface_color("accent") if theme else _ACCENT
        self._accent_hover = theme.surface_color("accent_hover") if theme else _ACCENT_HOVER
        self._accent_pressed = theme.surface_color("accent_pressed") if theme else _ACCENT_PRESSED
        self._foreground = theme.text_color("text") if theme else _FOREGROUND
        self._foreground_disabled = (
            theme.text_color("disabled_text") if theme else _FOREGROUND_DISABLED
        )
        self._disabled_mark = (
            theme.surface_color("disabled_text") if theme else _FOREGROUND_DISABLED
        )
        self._mark_surface = theme.surface_color("on_accent") if theme else _MARK
        self._knob_surface = theme.surface_color("text") if theme else _MARK
        self._text = str(text)
        self._checked = bool(checked)
        self._font_size = float(font_size)
        if self._font_size <= 0.0:
            raise ValueError("font_size must be greater than zero.")
        self._font_family = (
            font_family if font_family is not None else (theme.font_family if theme else "Segoe UI")
        ).strip()
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
        self._bind_theme(
            theme,
            {
                "_surface": ("surface", "raised", _SURFACE),
                "_surface_hover": ("surface", "hover", _SURFACE_HOVER),
                "_surface_focus": ("surface", "pressed", _SURFACE_FOCUS),
                "_surface_disabled": ("surface", "disabled", _SURFACE_DISABLED),
                "_accent": ("surface", "accent", _ACCENT),
                "_accent_hover": ("surface", "accent_hover", _ACCENT_HOVER),
                "_accent_pressed": ("surface", "accent_pressed", _ACCENT_PRESSED),
                "_foreground": ("text", "text", _FOREGROUND),
                "_foreground_disabled": ("text", "disabled_text", _FOREGROUND_DISABLED),
                "_disabled_mark": ("surface", "disabled_text", _FOREGROUND_DISABLED),
                "_mark_surface": ("surface", "on_accent", _MARK),
                "_knob_surface": ("surface", "text", _MARK),
                "_font_family": ("token", "font_family", "Segoe UI"),
            },
            {"_font_family": self._font_family if font_family is not None else None},
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
                    fill=self._foreground if self.enabled else self._foreground_disabled,
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

    def _add_indicator_face(
        self, root: SceneNode, bounds: Rect, radius: float, suffix: str
    ) -> Rect:
        def layer(name: str, fill: Color) -> None:
            root.add(SceneNode(
                key=f"{self.key}:{name}", kind=SceneNodeKind.RECTANGLE, bounds=bounds,
                fill=fill, corner_radius=CornerRadius.uniform(radius),
                z_index=1, hit_testable=False,
            ))

        if self._focused and self.enabled:
            focus = self._theme.surface_color("focus") if self._theme else _ACCENT_HOVER
            gap = self._theme.surface_color("canvas") if self._theme else _SURFACE
            unit = min(1.0, min(bounds.width, bounds.height) / 8)
            # Keep the entire cue inside even a tightly clipped control. The
            # separator distinguishes focus when a theme uses its accent for both.
            for name, color, inset in (("focus", focus, 2 * unit), ("focus-gap", gap, unit)):
                layer(name, color)
                bounds = Rect(bounds.x + inset, bounds.y + inset,
                              bounds.width - 2 * inset, bounds.height - 2 * inset)
                radius = max(0.0, radius - inset)
        layer(suffix, self._surface_color())
        return bounds

    def _mark_color(self) -> Color:
        if not self.enabled:
            return self._disabled_mark
        return self._mark_surface if self.checked else self._knob_surface

    def _surface_color(self) -> Color:
        if not self.enabled:
            return self._surface_disabled
        if self._checked:
            if self._pressed:
                return self._accent_pressed
            if self._hovered:
                return self._accent_hover
            return self._accent
        if self._pressed or self._focused:
            return self._surface_focus
        if self._hovered:
            return self._surface_hover
        return self._surface

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


@lru_cache(maxsize=32)
def _checkmark_path(size: float) -> Path2D:
    # Author the tick once for a 22-DIP face and reuse its triangles at each size.
    scale = size / 22
    outline = ((0, 5.5), (1.6, 3.9), (5, 7.3), (12.4, 0), (14, 1.6), (5, 10.5))
    return Path2D.polygon(*(Point(x * scale, y * scale) for x, y in outline))


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
        bounds = self._add_indicator_face(root, bounds, min(5.0, bounds.width * 0.24), "indicator")
        size = min(bounds.width, bounds.height)
        if not self.checked or size < 1:
            return
        path = _checkmark_path(size)
        ink = path.bounds
        mark = Rect(bounds.x + (bounds.width - ink.width) / 2,
                    bounds.y + (bounds.height - ink.height) / 2, ink.width, ink.height)
        root.add(SceneNode(
            key=f"{self.key}:mark", kind=SceneNodeKind.PATH, bounds=mark, path=path,
            fill=self._mark_color(),
            z_index=2, hit_testable=False,
        ))


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
        bounds = self._add_indicator_face(root, bounds, radius, "indicator")
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
                fill=self._mark_color(),
                corner_radius=CornerRadius.uniform(diameter * 0.5),
                hit_testable=False,
            )
        )


class _SwitchSlide(Tween):
    """A cancelled visual must still agree with the switch's committed value."""

    def cancel(self) -> bool:
        if not super().cancel():
            return False
        self.update(self.to_value)
        return True


class Switch(_ToggleControl):
    """Focusable on/off switch with optional theme-timed thumb travel.

    Supply the window's animation controller to slide the thumb when checked
    changes. The checked state and change event are immediate in both modes.
    """

    indicator_width = 40.0
    indicator_height = 22.0
    indicator_gap = 12.0

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        checked: bool = False,
        animations: AnimationController | None = None,
        key: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._animations = animations
        self._slide: _SwitchSlide | None = None
        self._position = float(bool(checked))
        super().__init__(
            text,
            bounds=bounds,
            checked=checked,
            key=key,
            role=AccessibilityRole.SWITCH,
            **kwargs,
        )

    def _set_checked(self, value: bool, *, input_event: Event | None) -> None:
        if value == self.checked:
            return
        if self._animations is None:
            self._position = float(value)
            super()._set_checked(value, input_event=input_event)
            return
        start, end = self._position, float(value)
        theme = self.effective_theme or DEFAULT_THEME
        controller = self._animations
        with state_transaction():
            self._cancel_slide()
            if (not controller.disposed
                    and self.mounted_window is controller.window and self.enabled and self.visible
                    and not theme.reduced_motion and theme.motion_duration and start != end):
                self._slide = _SwitchSlide(start, end, theme.motion_duration * abs(end - start),
                                           self._set_position, easing=ease_in_out_cubic)
                controller.play(self._slide)
            else:
                self._position = end
            super()._set_checked(value, input_event=input_event)

    def _set_position(self, value: float) -> None:
        if value != self._position:
            self._position = value
            self.invalidate(reason="switch_position")

    def _cancel_slide(self) -> None:
        if self._slide is not None and self._animations is not None:
            previous = self._slide
            self._slide = None
            self._animations.cancel(previous)

    def on_unmount(self, window: Window) -> None:
        self._cancel_slide()
        super().on_unmount(window)

    def on_theme_changed(self, previous: Theme | None, current: Theme | None) -> None:
        super().on_theme_changed(previous, current)
        if current and (current.reduced_motion or current.motion_duration == 0):
            self._cancel_slide()

    def _on_invalidated(self, event: Event) -> None:
        super()._on_invalidated(event)
        if (event.data.get("reason") in ("enabled", "visible")
                and not (self.enabled and self.visible)):
            self._cancel_slide()

    def _build_indicator(self, root: SceneNode, bounds: Rect) -> None:
        original_size = min(bounds.width, bounds.height)
        bounds = self._add_indicator_face(root, bounds, bounds.height * 0.5, "track")
        size = min(bounds.width, bounds.height)
        knob_size = max(0.0, original_size - 6.0) * (size / original_size)
        if knob_size <= 0.0:
            return
        margin = (size - knob_size) * 0.5
        left = bounds.x + margin
        right = bounds.right - margin - knob_size
        x = left + (right - left) * self._position
        y = bounds.y + ((bounds.height - knob_size) * 0.5)
        root.add(
            SceneNode(
                key=f"{self.key}:knob",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(x, y, knob_size, knob_size),
                z_index=2,
                fill=self._mark_color(),
                corner_radius=CornerRadius.uniform(knob_size * 0.5),
                hit_testable=False,
            )
        )
