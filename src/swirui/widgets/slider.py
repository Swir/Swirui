"""Retained slider and range-slider widgets."""

from __future__ import annotations

import math
from typing import Literal

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

ThumbName = Literal["lower", "upper"]

_VK_HOME = 0x24
_VK_END = 0x23
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_PAGE_UP = 0x21
_VK_PAGE_DOWN = 0x22

_TRACK = Color.from_hex("#263946")
_TRACK_DISABLED = Color.from_hex("#303A40")
_ACCENT = Color.from_hex("#0A98F0")
_ACCENT_HOVER = Color.from_hex("#28B2FF")
_THUMB = Color.from_hex("#F4FAFF")
_THUMB_DISABLED = Color.from_hex("#7A8992")
_FOCUS = Color.from_hex("#62E5FF")


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _snap(value: float, minimum: float, maximum: float, step: float) -> float:
    value = _clamp(float(value), minimum, maximum)
    steps = round((value - minimum) / step)
    snapped = minimum + (steps * step)
    return _clamp(snapped, minimum, maximum)


def _format_value(value: float) -> str:
    return f"{value:g}"


class Slider(Widget):
    """Focusable horizontal slider with retained GPU geometry."""

    thumb_size = 18.0
    track_height = 6.0

    def __init__(
        self,
        *,
        bounds: Rect,
        value: float = 0.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float = 1.0,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._minimum, self._maximum, self._step = _validate_range(minimum, maximum, step)
        self._value = _snap(value, self._minimum, self._maximum, self._step)
        self._hovered = False
        self._pressed = False
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
        self._sync_accessibility()
        self.on("pointer_enter", self._on_pointer_enter)
        self.on("pointer_leave", self._on_pointer_leave)
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)

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
        left, right, center_y = self._track_geometry()
        width = max(0.0, right - left)
        track = Rect(left, center_y - self.track_height / 2.0, width, self.track_height)
        root.add(
            SceneNode(
                key=f"{self.key}:track",
                kind=SceneNodeKind.RECTANGLE,
                bounds=track,
                fill=_TRACK if self.enabled else _TRACK_DISABLED,
                corner_radius=CornerRadius.uniform(self.track_height / 2.0),
                hit_testable=False,
            )
        )
        ratio = self._ratio(self._value)
        fill_width = width * ratio
        if fill_width > 0.0:
            root.add(
                SceneNode(
                    key=f"{self.key}:fill",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(left, track.y, fill_width, track.height),
                    z_index=1,
                    fill=_ACCENT if self.enabled else _TRACK_DISABLED,
                    corner_radius=CornerRadius.uniform(self.track_height / 2.0),
                    hit_testable=False,
                )
            )
        thumb = self._thumb_bounds(self._value)
        if self._focused and self.enabled:
            halo = 4.0
            root.add(
                SceneNode(
                    key=f"{self.key}:focus",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(
                        thumb.x - halo,
                        thumb.y - halo,
                        thumb.width + 2.0 * halo,
                        thumb.height + 2.0 * halo,
                    ),
                    z_index=2,
                    fill=_FOCUS.with_alpha(0.22),
                    corner_radius=CornerRadius.uniform((thumb.width + 2.0 * halo) / 2.0),
                    hit_testable=False,
                )
            )
        root.add(
            SceneNode(
                key=f"{self.key}:thumb",
                kind=SceneNodeKind.RECTANGLE,
                bounds=thumb,
                z_index=3,
                fill=self._thumb_color(),
                corner_radius=CornerRadius.uniform(thumb.width / 2.0),
                hit_testable=False,
            )
        )
        return root

    def _track_geometry(self) -> tuple[float, float, float]:
        inset = min(self.thumb_size / 2.0, self.bounds.width / 2.0)
        return (
            self.bounds.x + inset,
            self.bounds.right - inset,
            self.bounds.y + self.bounds.height / 2.0,
        )

    def _thumb_bounds(self, value: float) -> Rect:
        left, right, center_y = self._track_geometry()
        center_x = left + (right - left) * self._ratio(value)
        size = min(self.thumb_size, self.bounds.height, self.bounds.width)
        return Rect(center_x - size / 2.0, center_y - size / 2.0, size, size)

    def _ratio(self, value: float) -> float:
        return (value - self._minimum) / (self._maximum - self._minimum)

    def _value_from_x(self, x: float) -> float:
        left, right, _ = self._track_geometry()
        if right <= left:
            return self._minimum
        ratio = _clamp((x - left) / (right - left), 0.0, 1.0)
        return self._minimum + ratio * (self._maximum - self._minimum)

    def _set_value(self, value: float, *, input_event: Event | None) -> None:
        normalized = _snap(value, self._minimum, self._maximum, self._step)
        if normalized == self._value:
            return
        old_value = self._value
        self._value = normalized
        self._sync_accessibility()
        self.invalidate(reason="value")
        self.emit("changed", old_value=old_value, value=normalized, input_event=input_event)

    def _set_exact_endpoint(self, value: float, *, input_event: Event | None) -> None:
        normalized = _clamp(value, self._minimum, self._maximum)
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
            return _THUMB_DISABLED
        if self._hovered or self._pressed:
            return _ACCENT_HOVER
        return _THUMB

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.enabled and not self._hovered:
            self._hovered = True
            self.invalidate(reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        changed = self._hovered or self._pressed
        self._hovered = False
        self._pressed = False
        if changed:
            self.invalidate(reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if not self.enabled or native is None or native.button is not PointerButton.LEFT:
            return
        self._pressed = True
        if native.x is not None:
            self._set_value(self._value_from_x(native.x), input_event=event)
        self.invalidate(reason="pointer_down")

    def _on_pointer_move(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_MOVE)
        if self.enabled and self._pressed and native is not None and native.x is not None:
            self._set_value(self._value_from_x(native.x), input_event=event)

    def _on_pointer_up(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if native is None or native.button is not PointerButton.LEFT:
            return
        if self._pressed and native.x is not None and self.enabled:
            self._set_value(self._value_from_x(native.x), input_event=event)
        if self._pressed:
            self._pressed = False
            self.invalidate(reason="pointer_up")

    def _on_key_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or native is None or native.ctrl or native.alt or native.meta:
            return
        key = native.key_code
        if key in (_VK_LEFT, _VK_DOWN):
            self._set_value(self._value - self._step, input_event=event)
        elif key in (_VK_RIGHT, _VK_UP):
            self._set_value(self._value + self._step, input_event=event)
        elif key == _VK_PAGE_DOWN:
            self._set_value(self._value - self._step * 10.0, input_event=event)
        elif key == _VK_PAGE_UP:
            self._set_value(self._value + self._step * 10.0, input_event=event)
        elif key == _VK_HOME:
            self._set_exact_endpoint(self._minimum, input_event=event)
        elif key == _VK_END:
            self._set_exact_endpoint(self._maximum, input_event=event)
        else:
            return
        event.prevent_default()

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        changed = self._focused or self._pressed
        self._focused = False
        self._pressed = False
        if changed:
            self.invalidate(reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._hovered = False
            self._pressed = False

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        native = event.data.get("event")
        if isinstance(native, PlatformEvent) and native.kind is kind:
            return native
        return None


class RangeSlider(Widget):
    """Two-thumb horizontal slider for selecting a bounded interval."""

    thumb_size = 18.0
    track_height = 6.0

    def __init__(
        self,
        *,
        bounds: Rect,
        lower_value: float = 25.0,
        upper_value: float = 75.0,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float = 1.0,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._minimum, self._maximum, self._step = _validate_range(minimum, maximum, step)
        lower = _snap(lower_value, self._minimum, self._maximum, self._step)
        upper = _snap(upper_value, self._minimum, self._maximum, self._step)
        if lower > upper:
            raise ValueError("lower_value cannot be greater than upper_value.")
        self._lower_value = lower
        self._upper_value = upper
        self._active_thumb: ThumbName = "lower"
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
        self._sync_accessibility()
        self.on("pointer_enter", self._on_pointer_enter)
        self.on("pointer_leave", self._on_pointer_leave)
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)

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
        left, right, center_y = self._track_geometry()
        width = max(0.0, right - left)
        track = Rect(left, center_y - self.track_height / 2.0, width, self.track_height)
        root.add(
            SceneNode(
                key=f"{self.key}:track",
                kind=SceneNodeKind.RECTANGLE,
                bounds=track,
                fill=_TRACK if self.enabled else _TRACK_DISABLED,
                corner_radius=CornerRadius.uniform(self.track_height / 2.0),
                hit_testable=False,
            )
        )
        lower_x = left + width * self._ratio(self._lower_value)
        upper_x = left + width * self._ratio(self._upper_value)
        if upper_x > lower_x:
            root.add(
                SceneNode(
                    key=f"{self.key}:fill",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(lower_x, track.y, upper_x - lower_x, track.height),
                    z_index=1,
                    fill=_ACCENT if self.enabled else _TRACK_DISABLED,
                    corner_radius=CornerRadius.uniform(self.track_height / 2.0),
                    hit_testable=False,
                )
            )
        for name, value in (("lower", self._lower_value), ("upper", self._upper_value)):
            thumb = self._thumb_bounds(value)
            if self._focused and self.enabled and name == self._active_thumb:
                halo = 4.0
                root.add(
                    SceneNode(
                        key=f"{self.key}:{name}:focus",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            thumb.x - halo,
                            thumb.y - halo,
                            thumb.width + 2.0 * halo,
                            thumb.height + 2.0 * halo,
                        ),
                        z_index=2,
                        fill=_FOCUS.with_alpha(0.22),
                        corner_radius=CornerRadius.uniform((thumb.width + 2.0 * halo) / 2.0),
                        hit_testable=False,
                    )
                )
            root.add(
                SceneNode(
                    key=f"{self.key}:{name}:thumb",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=thumb,
                    z_index=3 if name == self._active_thumb else 2,
                    fill=self._thumb_color(name),
                    corner_radius=CornerRadius.uniform(thumb.width / 2.0),
                    hit_testable=False,
                )
            )
        return root

    def _track_geometry(self) -> tuple[float, float, float]:
        inset = min(self.thumb_size / 2.0, self.bounds.width / 2.0)
        return (
            self.bounds.x + inset,
            self.bounds.right - inset,
            self.bounds.y + self.bounds.height / 2.0,
        )

    def _ratio(self, value: float) -> float:
        return (value - self._minimum) / (self._maximum - self._minimum)

    def _thumb_bounds(self, value: float) -> Rect:
        left, right, center_y = self._track_geometry()
        center_x = left + (right - left) * self._ratio(value)
        size = min(self.thumb_size, self.bounds.height, self.bounds.width)
        return Rect(center_x - size / 2.0, center_y - size / 2.0, size, size)

    def _value_from_x(self, x: float) -> float:
        left, right, _ = self._track_geometry()
        if right <= left:
            return self._minimum
        ratio = _clamp((x - left) / (right - left), 0.0, 1.0)
        return self._minimum + ratio * (self._maximum - self._minimum)

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
        exact_endpoint: bool = False,
    ) -> None:
        normalized = (
            _clamp(value, self._minimum, self._maximum)
            if exact_endpoint
            else _snap(value, self._minimum, self._maximum, self._step)
        )
        old_lower = self._lower_value
        old_upper = self._upper_value
        self._active_thumb = thumb
        if thumb == "lower":
            self._lower_value = min(normalized, self._upper_value)
        else:
            self._upper_value = max(normalized, self._lower_value)
        if (old_lower, old_upper) == (self._lower_value, self._upper_value):
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
            return _THUMB_DISABLED
        if name == self._active_thumb and (self._hovered or self._dragging):
            return _ACCENT_HOVER
        return _THUMB

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.enabled and not self._hovered:
            self._hovered = True
            self.invalidate(reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        changed = self._hovered or self._dragging
        self._hovered = False
        self._dragging = False
        if changed:
            self.invalidate(reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or native is None
            or native.button is not PointerButton.LEFT
            or native.x is None
        ):
            return
        value = self._value_from_x(native.x)
        self._active_thumb = self._nearest_thumb(value)
        self._dragging = True
        self._set_thumb_value(self._active_thumb, value, input_event=event)
        self.invalidate(reason="pointer_down")

    def _on_pointer_move(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_MOVE)
        if self.enabled and self._dragging and native is not None and native.x is not None:
            self._set_thumb_value(
                self._active_thumb,
                self._value_from_x(native.x),
                input_event=event,
            )

    def _on_pointer_up(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if native is None or native.button is not PointerButton.LEFT:
            return
        if self.enabled and self._dragging and native.x is not None:
            self._set_thumb_value(
                self._active_thumb,
                self._value_from_x(native.x),
                input_event=event,
            )
        if self._dragging:
            self._dragging = False
            self.invalidate(reason="pointer_up")

    def _on_key_down(self, event: Event) -> None:
        native = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or native is None or native.ctrl or native.alt or native.meta:
            return
        current = self._lower_value if self._active_thumb == "lower" else self._upper_value
        key = native.key_code
        exact = False
        if key in (_VK_LEFT, _VK_DOWN):
            target = current - self._step
        elif key in (_VK_RIGHT, _VK_UP):
            target = current + self._step
        elif key == _VK_PAGE_DOWN:
            target = current - self._step * 10.0
        elif key == _VK_PAGE_UP:
            target = current + self._step * 10.0
        elif key == _VK_HOME:
            target = self._minimum
            exact = True
        elif key == _VK_END:
            target = self._maximum
            exact = True
        else:
            return
        self._set_thumb_value(
            self._active_thumb,
            target,
            input_event=event,
            exact_endpoint=exact,
        )
        event.prevent_default()

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        changed = self._focused or self._dragging
        self._focused = False
        self._dragging = False
        if changed:
            self.invalidate(reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._hovered = False
            self._dragging = False

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        native = event.data.get("event")
        if isinstance(native, PlatformEvent) and native.kind is kind:
            return native
        return None
