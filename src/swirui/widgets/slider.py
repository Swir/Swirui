"""Retained slider and range-slider widgets."""

from __future__ import annotations

import math
from abc import abstractmethod
from fractions import Fraction
from typing import TYPE_CHECKING, Literal

from swirui.core import (
    AccessibilityNode,
    AccessibilityRole,
    Component,
    Event,
    build_accessibility_tree,
)
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Path2D, Point, Rect
from swirui.rendering.gradients import LinearGradient
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import Theme

from .base import ThemeStyle, Widget, _gradient_track_fill

if TYPE_CHECKING:
    from swirui.window import Window

ThumbName = Literal["lower", "upper"]

_VK_HOME = 0x24
_VK_END = 0x23
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_PAGE_UP = 0x21
_VK_PAGE_DOWN = 0x22
_KEY_STEPS = {
    _VK_LEFT: -1, _VK_DOWN: -1, _VK_RIGHT: 1, _VK_UP: 1,
    _VK_PAGE_DOWN: -10, _VK_PAGE_UP: 10,
}

_TRACK = Color.from_hex("#263946")
_TRACK_DISABLED = Color.from_hex("#303A40")
_ACCENT = Color.from_hex("#0A98F0")
_ACCENT_HOVER = Color.from_hex("#28B2FF")
_THUMB = Color.from_hex("#F4FAFF")
_THUMB_DISABLED = Color.from_hex("#7A8992")
_FOCUS = Color.from_hex("#62E5FF")
_THUMB_MARKS = {
    "lower": Path2D.polygon(Point(0, 3), Point(5, 0), Point(5, 6)),
    "upper": Path2D.polygon(Point(0, 0), Point(5, 3), Point(0, 6)),
}


def _slider_theme_styles() -> dict[str, ThemeStyle]:
    return {
        "_track": ("surface", "border", _TRACK),
        "_track_disabled": ("surface", "disabled", _TRACK_DISABLED),
        "_accent": ("surface", "accent", _ACCENT),
        "_accent_hover": ("surface", "accent_hover", _ACCENT_HOVER),
        "_thumb": ("surface", "text", _THUMB),
        "_thumb_disabled": ("surface", "disabled_text", _THUMB_DISABLED),
        "_focus": ("surface", "focus", _FOCUS),
    }


def _validate_range(minimum: float, maximum: float, step: float) -> tuple[float, float, float]:
    minimum = float(minimum)
    maximum = float(maximum)
    step = float(step)
    if not all(math.isfinite(value) for value in (minimum, maximum, step)):
        raise ValueError("minimum, maximum and step must be finite.")
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum.")
    if step <= 0.0:
        raise ValueError("step must be greater than zero.")
    return minimum, maximum, step


def _format_value(value: float) -> str:
    return f"{value:g}"


class _SliderBase(Widget):
    thumb_size = 18.0
    track_height = 6.0
    _minimum: float
    _maximum: float
    _hovered: bool
    _focused: bool
    _dragging: bool
    _focus: Color
    _step: float
    _track: Color
    _accent: Color
    _track_disabled: Color
    _fill_gradient: LinearGradient | None = None

    @property
    def fill_gradient(self) -> LinearGradient | None:
        """Full-track color scale revealed between the selected limits."""
        return self._fill_gradient

    @fill_gradient.setter
    def fill_gradient(self, value: LinearGradient | None) -> None:
        if value is not None and not isinstance(value, LinearGradient):
            raise TypeError("fill_gradient must be a LinearGradient or None.")
        if value != self._fill_gradient:
            self._fill_gradient = value
            self.invalidate(reason="fill_gradient")

    def _configure_steps(self, minimum: float, maximum: float, step: float) -> None:
        self._minimum, self._maximum, self._step = _validate_range(minimum, maximum, step)
        # Decimal scales such as 0..0.07 by 0.01 have exactly seven intervals.
        self._origin = Fraction(str(self._minimum))
        self._increment = Fraction(str(self._step))
        end = self._tick_position(self._maximum)
        self._last_tick = math.ceil(end)
        self._last_midpoint = (self._last_tick - 1 + end) / 2

    def _tick_position(self, value: float) -> Fraction:
        return (Fraction(str(value)) - self._origin) / self._increment

    def _value_at_tick(self, tick: int) -> float:
        if tick <= 0:
            return self._minimum
        if tick >= self._last_tick:
            return self._maximum
        return float(self._origin + tick * self._increment)

    def _snap(self, value: float) -> float:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("value must be finite.")
        if value <= self._minimum:
            return self._minimum
        if value >= self._maximum:
            return self._maximum
        position = self._tick_position(value)
        if position > self._last_midpoint:
            return self._maximum
        return self._value_at_tick(round(position))

    def _keyboard_value(self, current: float, key: int | None) -> float | None:
        if key == _VK_HOME:
            return self._minimum
        if key == _VK_END:
            return self._maximum
        if key is None or key not in _KEY_STEPS:
            return None
        tick = self._last_tick if current == self._maximum else round(self._tick_position(current))
        return self._value_at_tick(tick + _KEY_STEPS[key])

    def _bind_drag(self) -> None:
        self.on("pointer_enter", self._on_pointer_enter)
        self.on("pointer_leave", self._on_pointer_leave)
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
        self.on("pointer_capture_lost", self._on_capture_lost)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)

    def on_unmount(self, window: Window) -> None:
        window.release_pointer_capture(self)
        super().on_unmount(window)

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.enabled and not self._hovered:
            self._hovered = True
            self.invalidate(reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        if self._hovered:
            self._hovered = False
            self.invalidate(reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (event.source is not self or event.default_prevented or not self.enabled
                or native is None or native.button is not PointerButton.LEFT or native.x is None):
            return
        window = self.mounted_window
        path = event.data.get("component_path", ())
        if any(not item.enabled or not item.visible for item in path):
            return
        self._dragging = True
        if window is not None:
            window.capture_pointer(self)
        if self._dragging:
            self._update_drag(native.x, event, initial=True)
            self.invalidate(reason="pointer_down")

    def _on_pointer_move(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_MOVE)
        if self._dragging and self.enabled and native is not None and native.x is not None:
            self._update_drag(native.x, event)

    def _on_pointer_up(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if not self._dragging or native is None or native.button is not PointerButton.LEFT:
            return
        self._dragging = False
        if self.enabled and native.x is not None:
            self._update_drag(native.x, event)
        self.invalidate(reason="pointer_up")

    @abstractmethod
    def _update_drag(self, x: float, event: Event, *, initial: bool = False) -> None:
        """Apply a horizontal pointer position during a captured drag."""

    def _on_capture_lost(self, _event: Event) -> None:
        if self._dragging:
            self._dragging = False
            self.invalidate(reason="pointer_capture_lost")

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        changed = self._focused or self._dragging
        self._focused = self._dragging = False
        if self.mounted_window is not None:
            self.mounted_window.release_pointer_capture(self)
        if changed:
            self.invalidate(reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if (event.data.get("reason") in ("enabled", "visible")
                and not (self.enabled and self.visible)):
            self._hovered = self._dragging = False
            if self.mounted_window is not None:
                self.mounted_window.release_pointer_capture(self)

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        native = event.data.get("event")
        if isinstance(native, PlatformEvent) and native.kind is kind:
            return native
        return None

    def _track_geometry(self) -> tuple[float, float, float]:
        inset = min(self.thumb_size / 2.0, self.bounds.width / 2.0)
        return (
            self.bounds.x + inset,
            self.bounds.right - inset,
            self.bounds.y + self.bounds.height / 2.0,
        )

    def _add_track(self, root: SceneNode, lower: float, upper: float) -> None:
        left, right, center_y = self._track_geometry()
        track = Rect(left, center_y - self.track_height / 2, max(0.0, right - left),
                     self.track_height)
        radius = CornerRadius.uniform(self.track_height / 2)
        root.add(SceneNode(
            f"{self.key}:track", SceneNodeKind.RECTANGLE, track,
            fill=self._track if self.enabled else self._track_disabled,
            corner_radius=radius, hit_testable=False,
        ))
        start = track.x + track.width * self._ratio(lower)
        end = track.x + track.width * self._ratio(upper)
        if end <= start or track.height <= 0:
            return
        filled = Rect(start, track.y, end - start, track.height)
        key = f"{self.key}:fill"
        if self.enabled and self.fill_gradient is not None:
            fill = _gradient_track_fill(self.fill_gradient, key, track, filled, radius)
        else:
            fill = SceneNode(
                key, SceneNodeKind.RECTANGLE, filled, z_index=1,
                fill=self._accent if self.enabled else self._track_disabled,
                corner_radius=radius, hit_testable=False,
            )
        root.add(fill)

    def _thumb_bounds(self, value: float) -> Rect:
        left, right, center_y = self._track_geometry()
        center_x = left + (right - left) * self._ratio(value)
        size = min(self.thumb_size, self.bounds.height, self.bounds.width)
        return Rect(center_x - size / 2.0, center_y - size / 2.0, size, size)

    def _ratio(self, value: float) -> float:
        return (value - self._minimum) / (self._maximum - self._minimum)

    def _add_thumb(self, root: SceneNode, key: str, value: float, fill: Color,
                   *, active: bool, direction: ThumbName | None = None) -> None:
        bounds = self._thumb_bounds(value)
        z = 3 if active else 2
        if active and self._focused and self.enabled and bounds.width > 0:
            gap = self._theme.surface_color("canvas") if self._theme else _TRACK
            unit = min(1.0, bounds.width / 8)
            rings = (("focus", self._focus, 2 * unit), ("focus-gap", gap, unit))
            for suffix, color, inset in rings:
                root.add(SceneNode(f"{key}:{suffix}", SceneNodeKind.RECTANGLE, bounds,
                                   fill=color, corner_radius=CornerRadius.uniform(bounds.width / 2),
                                   z_index=z, hit_testable=False))
                bounds = Rect(bounds.x + inset, bounds.y + inset,
                              bounds.width - 2 * inset, bounds.height - 2 * inset)
            if direction is not None and bounds.width >= 8:
                mark = Rect(bounds.x + (bounds.width - 5) / 2, bounds.y + (bounds.height - 6) / 2,
                            5, 6)
                root.add(SceneNode(f"{key}:direction", SceneNodeKind.PATH, mark,
                                   path=_THUMB_MARKS[direction], fill=gap, z_index=z + 1,
                                   hit_testable=False))
        root.add(SceneNode(f"{key}:thumb", SceneNodeKind.RECTANGLE, bounds, fill=fill,
                           corner_radius=CornerRadius.uniform(bounds.width / 2),
                           z_index=z, hit_testable=False))

    def _value_from_x(self, x: float) -> float:
        left, right, _ = self._track_geometry()
        if right <= left or x <= left:
            return self._minimum
        if x >= right:
            return self._maximum
        ratio = (x - left) / (right - left)
        return self._minimum + ratio * (self._maximum - self._minimum)


class Slider(_SliderBase):
    """Focusable horizontal slider with retained GPU geometry."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float = 1.0,
        fill_gradient: LinearGradient | None = None,
        key: str | None = None,
        theme: Theme | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._track = theme.surface_color("border") if theme else _TRACK
        self._track_disabled = theme.surface_color("disabled") if theme else _TRACK_DISABLED
        self._accent = theme.surface_color("accent") if theme else _ACCENT
        self._accent_hover = theme.surface_color("accent_hover") if theme else _ACCENT_HOVER
        self._thumb = theme.surface_color("text") if theme else _THUMB
        self._thumb_disabled = theme.surface_color("disabled_text") if theme else _THUMB_DISABLED
        self._focus = theme.surface_color("focus") if theme else _FOCUS
        self._configure_steps(minimum, maximum, step)
        self._value = self._snap(value)
        self._hovered = False
        self._dragging = False
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.SLIDER,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._bind_theme(theme, _slider_theme_styles())
        self.fill_gradient = fill_gradient
        self._sync_accessibility()
        self._bind_drag()
        self.on("key_down", self._on_key_down)

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def maximum(self) -> float:
        return self._maximum

    @property
    def step(self) -> float:
        return self._step

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._set_value(value, input_event=None)

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=Color(0.0, 0.0, 0.0, 0.0),
            hit_testable=self.enabled,
        )
        self._add_track(root, self.minimum, self.value)
        self._add_thumb(root, self.key, self._value, self._thumb_color(), active=True)
        return root

    def _set_value(self, value: float, *, input_event: Event | None) -> None:
        normalized = self._snap(value)
        if normalized == self._value:
            return
        old_value = self._value
        self._value = normalized
        self._sync_accessibility()
        self.invalidate(reason="value")
        self.emit("changed", old_value=old_value, value=normalized, input_event=input_event)

    def _sync_accessibility(self) -> None:
        self.accessible_value = self._value
        self.accessible_min_value = self._minimum
        self.accessible_max_value = self._maximum
        self.accessible_value_text = _format_value(self._value)

    def _thumb_color(self) -> Color:
        if not self.enabled:
            return self._thumb_disabled
        if self._hovered or self._dragging:
            return self._accent_hover
        return self._thumb

    def _update_drag(self, x: float, event: Event, *, initial: bool = False) -> None:
        value = self._value_from_x(x)
        self._set_value(value, input_event=event)

    def _on_key_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or native is None or native.ctrl or native.alt or native.meta:
            return
        target = self._keyboard_value(self._value, native.key_code)
        if target is None:
            return
        self._set_value(target, input_event=event)
        event.prevent_default()


class RangeSlider(_SliderBase):
    """Two-thumb horizontal slider for selecting a bounded interval."""

    def __init__(
        self,
        *,
        bounds: Rect,
        lower_value: float = 25.0,
        upper_value: float = 75.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float = 1.0,
        fill_gradient: LinearGradient | None = None,
        key: str | None = None,
        theme: Theme | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._track = theme.surface_color("border") if theme else _TRACK
        self._track_disabled = theme.surface_color("disabled") if theme else _TRACK_DISABLED
        self._accent = theme.surface_color("accent") if theme else _ACCENT
        self._accent_hover = theme.surface_color("accent_hover") if theme else _ACCENT_HOVER
        self._thumb = theme.surface_color("text") if theme else _THUMB
        self._thumb_disabled = theme.surface_color("disabled_text") if theme else _THUMB_DISABLED
        self._focus = theme.surface_color("focus") if theme else _FOCUS
        self._configure_steps(minimum, maximum, step)
        lower = self._snap(lower_value)
        upper = self._snap(upper_value)
        if lower > upper:
            raise ValueError("lower_value cannot be greater than upper_value.")
        self._lower_value = lower
        self._upper_value = upper
        self._active_thumb: ThumbName = "lower"
        self._drag_thumb: ThumbName | None = None
        self._grab_offset_x = 0.0
        self._hovered = False
        self._dragging = False
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.SLIDER,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._bind_theme(theme, _slider_theme_styles())
        self.fill_gradient = fill_gradient
        self._sync_accessibility()
        self._bind_drag()
        self.on("key_down", self._on_key_down)

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def maximum(self) -> float:
        return self._maximum

    @property
    def step(self) -> float:
        return self._step

    @property
    def lower_value(self) -> float:
        return self._lower_value

    @lower_value.setter
    def lower_value(self, value: float) -> None:
        self._set_thumb_value("lower", value, input_event=None)

    @property
    def upper_value(self) -> float:
        return self._upper_value

    @upper_value.setter
    def upper_value(self, value: float) -> None:
        self._set_thumb_value("upper", value, input_event=None)

    @property
    def active_thumb(self) -> ThumbName:
        return self._active_thumb

    def accessibility_snapshot(self, *, focused: Component | None = None) -> AccessibilityNode:
        limits = (("lower", self.lower_value, self.minimum, self.upper_value),
                  ("upper", self.upper_value, self.lower_value, self.maximum))
        thumbs = tuple(AccessibilityNode(
            key=f"{self.key}:a11y:{name}", role=AccessibilityRole.SLIDER,
            name=f"{name.title()} limit", description=None, enabled=self.enabled,
            focusable=self.focusable, focused=focused is self and name == self.active_thumb,
            active=name == self.active_thumb, value=value, min_value=low, max_value=high,
            value_text=_format_value(value),
        ) for name, value, low, high in limits)
        children = tuple(node for child in self.children
                         if (node := build_accessibility_tree(child, focused=focused)) is not None)
        return AccessibilityNode(
            key=self.key, role=self.accessibility_role, name=self.accessible_name or self.name,
            description=self.accessible_description, enabled=self.enabled, focusable=self.focusable,
            focused=focused is self, checked=self.accessible_checked, value=self.accessible_value,
            min_value=self.accessible_min_value, max_value=self.accessible_max_value,
            value_text=self.accessible_value_text, children=thumbs + children,
        )

    def _step_keyboard_focus(self, *, reverse: bool, entering: bool) -> bool:
        if self._dragging:
            return False
        order: tuple[ThumbName, ThumbName] = ("upper", "lower") if reverse else ("lower", "upper")
        thumb = order[0] if entering else order[1]
        if thumb == self._active_thumb:
            return False
        self._active_thumb = thumb
        self.invalidate(reason="active_thumb")
        return True

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=Color(0.0, 0.0, 0.0, 0.0),
            hit_testable=self.enabled,
        )
        self._add_track(root, self.lower_value, self.upper_value)
        for name, value in (("lower", self._lower_value), ("upper", self._upper_value)):
            self._add_thumb(root, f"{self.key}:{name}", value, self._thumb_color(name),
                            active=name == self._active_thumb, direction=self._active_thumb)
        return root

    def _nearest_thumb(self, value: float) -> ThumbName:
        lower_distance = abs(value - self._lower_value)
        upper_distance = abs(value - self._upper_value)
        if lower_distance == upper_distance:
            return self._active_thumb
        return "lower" if lower_distance < upper_distance else "upper"

    def _set_thumb_value(
        self,
        thumb: ThumbName,
        value: float,
        *,
        input_event: Event | None,
    ) -> None:
        normalized = self._snap(value)
        self._apply_thumb_value(thumb, normalized, input_event)

    def _apply_thumb_value(self, thumb: ThumbName, value: float, input_event: Event | None) -> None:
        old_lower = self._lower_value
        old_upper = self._upper_value
        old_thumb = self._active_thumb
        self._active_thumb = thumb
        if thumb == "lower":
            self._lower_value = min(value, self._upper_value)
        else:
            self._upper_value = max(value, self._lower_value)
        if (old_lower, old_upper) == (self._lower_value, self._upper_value):
            if old_thumb != thumb:
                self.invalidate(reason="active_thumb")
            return
        self._sync_accessibility()
        self.invalidate(reason="value")
        self.emit(
            "changed",
            old_lower=old_lower,
            old_upper=old_upper,
            lower_value=self._lower_value,
            upper_value=self._upper_value,
            active_thumb=thumb,
            input_event=input_event,
        )

    def _sync_accessibility(self) -> None:
        self.accessible_value = None
        self.accessible_min_value = self._minimum
        self.accessible_max_value = self._maximum
        self.accessible_value_text = (
            f"{_format_value(self._lower_value)}–{_format_value(self._upper_value)}"
        )

    def _thumb_color(self, name: str) -> Color:
        if not self.enabled:
            return self._thumb_disabled
        if name == self._active_thumb and (self._hovered or self._dragging):
            return self._accent_hover
        return self._thumb

    def _update_drag(self, x: float, event: Event, *, initial: bool = False) -> None:
        if initial:
            self._drag_thumb = None
            self._grab_offset_x = 0.0
            if self._lower_value == self._upper_value:
                shared = self._thumb_bounds(self._lower_value)
                if shared.x <= x <= shared.right:
                    self._grab_offset_x = x - (shared.x + shared.width / 2)

        raw = self._value_from_x(x - self._grab_offset_x)
        value = self._snap(raw)
        if self._drag_thumb is None:
            if self._lower_value != self._upper_value:
                self._drag_thumb = self._nearest_thumb(raw)
            elif value == self._lower_value:
                return
            else:
                self._drag_thumb = "lower" if value < self._lower_value else "upper"
        self._apply_thumb_value(self._drag_thumb, value, event)

    def _on_key_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or native is None or native.ctrl or native.alt or native.meta:
            return
        current = self._lower_value if self._active_thumb == "lower" else self._upper_value
        target = self._keyboard_value(current, native.key_code)
        if target is None:
            return
        self._apply_thumb_value(self._active_thumb, target, event)
        event.prevent_default()
