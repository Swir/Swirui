"""Retained professional color picker for SwirUI."""

from __future__ import annotations

import colorsys
import math
from typing import Literal

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Path2D, Point, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import Theme

from .base import Widget

ColorChannel = Literal["hue", "saturation", "value", "alpha"]

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_BACKGROUND = Color.from_hex("#06101A")
_SURFACE = Color.from_hex("#0A1824")
_BORDER = Color.from_hex("#164D6B")
_FOREGROUND = Color.from_hex("#E9F8FF")
_MUTED = Color.from_hex("#8DA8B8")
_ACCENT = Color.from_hex("#62E5FF")
_DISABLED = Color.from_hex("#456273")
_CHANNELS: tuple[ColorChannel, ...] = ("hue", "saturation", "value", "alpha")
_LABELS: dict[ColorChannel, str] = {
    "hue": "Hue",
    "saturation": "Saturation",
    "value": "Value",
    "alpha": "Alpha",
}


def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
    candidate = event.data.get("event")
    if isinstance(candidate, PlatformEvent) and candidate.kind is kind:
        return candidate
    return None


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _linear_color(color: Color) -> Color:
    """ColorPicker values and HEX are encoded sRGB; native shapes are linear."""
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    return Color(channel(color.r), channel(color.g), channel(color.b), color.a)


def _hex_channel(value: float) -> int:
    return max(0, min(255, round(_clamp_unit(value) * 255.0)))


def _text(
    key: str,
    bounds: Rect,
    value: str,
    size: float,
    color: Color,
    family: str,
    *,
    z_index: int = 5,
) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.TEXT,
        bounds=bounds,
        fill=color,
        text=value,
        font_size=size,
        font_family=family,
        z_index=z_index,
        hit_testable=False,
    )


class ColorPicker(Widget):
    """Focusable HSV(A) color picker with retained gradient tracks.

    Values, HSV channels and HEX use encoded sRGB; swatches and tracks convert
    to linear RGB for native rendering while preserving alpha.
    Python remains the public API while every visual compiles into ordinary
    retained ``SceneNode`` primitives, so the existing Rust/wgpu pipeline owns
    native GPU submission without a separate widget renderer.
    """

    _PADDING = 14.0
    _PREVIEW_HEIGHT = 44.0
    _LABEL_HEIGHT = 16.0
    _TRACK_HEIGHT = 18.0
    _CHANNEL_GAP = 12.0
    _GRADIENT_SEGMENTS = 128
    _background: Color
    _surface: Color
    _border: Color
    _foreground: Color
    _muted: Color
    _accent: Color
    _accent_surface: Color
    _disabled_text: Color
    _disabled_surface: Color
    _corner_radius: float

    def __init__(
        self,
        *,
        bounds: Rect,
        value: Color | None = None,
        show_alpha: bool = True,
        key: str | None = None,
        font_family: str | None = None,
        theme: Theme | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Color picker",
        accessible_description: str | None = None,
    ) -> None:
        initial = value or Color.from_hex("#0088FFFF")
        if not isinstance(initial, Color):
            raise TypeError("value must be a swirui.rendering.Color.")
        family = "Segoe UI" if font_family is None else str(font_family).strip()
        if not family:
            raise ValueError("font_family must not be empty.")
        hue, saturation, brightness = colorsys.rgb_to_hsv(initial.r, initial.g, initial.b)
        self._hue = float(hue)
        self._saturation = float(saturation)
        self._value = float(brightness)
        self._alpha = float(initial.a if show_alpha else 1.0)
        self._show_alpha = bool(show_alpha)
        self._font_family = family
        self._active_channel: ColorChannel = "hue"
        self._drag_channel: ColorChannel | None = None
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._bind_theme(
            theme,
            {
                "_background": ("surface", "surface", _BACKGROUND),
                "_surface": ("surface", "raised", _SURFACE),
                "_border": ("surface", "border", _BORDER),
                "_foreground": ("text", "text", _FOREGROUND),
                "_muted": ("text", "muted", _MUTED),
                "_accent": ("text", "accent", _ACCENT),
                "_accent_surface": ("surface", "accent", _ACCENT),
                "_disabled_text": ("text", "disabled_text", _DISABLED),
                "_disabled_surface": ("surface", "disabled", _DISABLED),
                "_corner_radius": ("token", "control_radius", 10.0),
                "_font_family": ("token", "font_family", "Segoe UI"),
            },
            {"_font_family": family if font_family is not None else None},
        )
        self._enable_theme_focus_frame()
        self._sync_accessibility()
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("pointer_capture_lost", self._on_capture_lost)

    @property
    def value(self) -> Color:
        red, green, blue = colorsys.hsv_to_rgb(self._hue, self._saturation, self._value)
        return Color(float(red), float(green), float(blue), self._alpha)

    @value.setter
    def value(self, value: Color) -> None:
        self.set_color(value)

    @property
    def show_alpha(self) -> bool:
        return self._show_alpha

    @property
    def active_channel(self) -> ColorChannel:
        return self._active_channel

    @property
    def hex_value(self) -> str:
        color = self.value
        rgb = f"#{_hex_channel(color.r):02X}{_hex_channel(color.g):02X}{_hex_channel(color.b):02X}"
        if not self._show_alpha:
            return rgb
        return f"{rgb}{_hex_channel(color.a):02X}"

    def set_hex(self, value: str) -> ColorPicker:
        return self.set_color(Color.from_hex(value))

    def set_color(self, value: Color, *, input_event: Event | None = None) -> ColorPicker:
        if not isinstance(value, Color):
            raise TypeError("value must be a swirui.rendering.Color.")
        old = self.value
        hue, saturation, brightness = colorsys.rgb_to_hsv(value.r, value.g, value.b)
        self._hue = float(hue)
        self._saturation = float(saturation)
        self._value = float(brightness)
        self._alpha = float(value.a if self._show_alpha else 1.0)
        self._publish_change(old, input_event=input_event)
        return self

    def activate_channel(self, channel: ColorChannel) -> ColorPicker:
        if channel not in self.channels:
            raise ValueError(f"Channel {channel!r} is not available.")
        if channel != self._active_channel:
            self._active_channel = channel
            self.invalidate(reason="active_channel")
        return self

    def set_channel_value(
        self,
        channel: ColorChannel,
        value: float,
        *,
        input_event: Event | None = None,
    ) -> ColorPicker:
        if channel not in self.channels:
            raise ValueError(f"Channel {channel!r} is not available.")
        normalized = _clamp_unit(value)
        old = self.value
        if channel == "hue":
            self._hue = normalized
        elif channel == "saturation":
            self._saturation = normalized
        elif channel == "value":
            self._value = normalized
        else:
            self._alpha = normalized
        self._publish_change(old, input_event=input_event)
        return self

    def adjust_active(self, steps: int = 1, *, coarse: bool = False) -> ColorPicker:
        step = (10.0 if coarse else 1.0) / (360.0 if self._active_channel == "hue" else 100.0)
        return self.set_channel_value(
            self._active_channel,
            self.channel_value(self._active_channel) + float(steps) * step,
        )

    @property
    def channels(self) -> tuple[ColorChannel, ...]:
        return _CHANNELS if self._show_alpha else _CHANNELS[:-1]

    def channel_value(self, channel: ColorChannel) -> float:
        if channel not in self.channels:
            raise ValueError(f"Channel {channel!r} is not available.")
        if channel == "hue":
            return self._hue
        if channel == "saturation":
            return self._saturation
        if channel == "value":
            return self._value
        return self._alpha

    def track_bounds(self, channel: ColorChannel) -> Rect:
        if channel not in self.channels:
            raise ValueError(f"Channel {channel!r} is not available.")
        index = self.channels.index(channel)
        track_top = (
            self.bounds.y
            + self._PADDING
            + self._PREVIEW_HEIGHT
            + self._CHANNEL_GAP
            + index * (self._LABEL_HEIGHT + self._TRACK_HEIGHT + self._CHANNEL_GAP)
            + self._LABEL_HEIGHT
        )
        return Rect(
            self.bounds.x + self._PADDING,
            track_top,
            max(0.0, self.bounds.width - self._PADDING * 2.0),
            self._TRACK_HEIGHT,
        )

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        preview = Rect(
            self.bounds.x + self._PADDING,
            self.bounds.y + self._PADDING,
            min(112.0, max(0.0, self.bounds.width * 0.28)),
            self._PREVIEW_HEIGHT,
        )
        self._append_checkerboard(root, preview, "preview")
        root.add(
            SceneNode(
                key=f"{self.key}:preview",
                kind=SceneNodeKind.RECTANGLE,
                bounds=preview,
                fill=_linear_color(self.value) if self.enabled else self._disabled_surface,
                corner_radius=CornerRadius.uniform(0.0),
                z_index=2,
                hit_testable=False,
            ),
            _text(
                f"{self.key}:hex",
                Rect(
                    preview.right + 14.0,
                    preview.y + 8.0,
                    max(0.0, self.bounds.right - preview.right - self._PADDING - 14.0),
                    28.0,
                ),
                self.hex_value,
                18.0,
                self._foreground if self.enabled else self._disabled_text,
                self._font_family,
            ),
        )
        if self._focused and self.enabled and self._theme is None:
            root.add(
                SceneNode(
                    key=f"{self.key}:focus",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(
                        self.bounds.x + 2.0,
                        self.bounds.y + 2.0,
                        max(0.0, self.bounds.width - 4.0),
                        max(0.0, self.bounds.height - 4.0),
                    ),
                    fill=self._accent_surface.with_alpha(0.05),
                    corner_radius=CornerRadius.uniform(9.0),
                    z_index=1,
                    hit_testable=False,
                )
            )
        for channel in self.channels:
            self._append_channel(root, channel)
        self._add_theme_focus_frame(root)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:{channel}",
                role=AccessibilityRole.SLIDER,
                name=_LABELS[channel],
                description="Color channel",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                value=self._accessibility_value(channel),
                min_value=0.0,
                max_value=360.0 if channel == "hue" else 100.0,
                value_text=self._channel_text(channel),
                selected=channel == self._active_channel,
                active=channel == self._active_channel,
            )
            for channel in self.channels
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.hex_value,
            column_count=len(children),
            children=children,
        )

    def _append_channel(self, root: SceneNode, channel: ColorChannel) -> None:
        track = self.track_bounds(channel)
        label_y = track.y - self._LABEL_HEIGHT
        root.add(
            _text(
                f"{self.key}:label:{channel}",
                Rect(track.x, label_y, max(0.0, track.width - 70.0), self._LABEL_HEIGHT),
                _LABELS[channel],
                11.0,
                (self._disabled_text if not self.enabled else self._accent
                 if channel == self._active_channel else self._muted),
                self._font_family,
            ),
            _text(
                f"{self.key}:value:{channel}",
                Rect(track.right - 68.0, label_y, 68.0, self._LABEL_HEIGHT),
                self._channel_text(channel),
                11.0,
                self._foreground if self.enabled else self._disabled_text,
                self._font_family,
            ),
        )
        if track.width <= 0 or track.height <= 0:
            return
        if channel == "alpha":
            self._append_checkerboard(root, track, "alpha")
        segments = min(self._GRADIENT_SEGMENTS, max(16, math.ceil(track.width / 2)))
        segment_width = track.width / segments
        for index in range(segments):
            x = track.x + index * segment_width
            width = segment_width if index < segments - 1 else track.right - x
            ratio = (index + 0.5) / segments
            root.add(
                SceneNode(
                    key=f"{self.key}:track:{channel}:{index}",
                    kind=SceneNodeKind.PATH,
                    bounds=Rect(x, track.y, max(0.0, width), track.height),
                    path=Path2D((Point(0, 0), Point(width, 0),
                                 Point(width, track.height), Point(0, track.height))),
                    fill=(_linear_color(self._gradient_color(channel, ratio))
                          if self.enabled else self._disabled_surface),
                    z_index=2,
                    hit_testable=False,
                )
            )
        thumb_x = track.x + track.width * self.channel_value(channel)
        thumb_left = max(track.x, min(track.right - 3.0, thumb_x - 1.5))
        # A dark outline and white center remain visible over every hue/value,
        # independently of the application's light or dark appearance.
        root.add(SceneNode(
            key=f"{self.key}:thumb-outline:{channel}",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(thumb_left - 1.0, track.y - 4.0, 5.0, track.height + 8.0),
            fill=Color(0, 0, 0) if self.enabled else self._border,
            corner_radius=CornerRadius.uniform(2.5),
            z_index=3,
            hit_testable=False,
        ))
        root.add(
            SceneNode(
                key=f"{self.key}:thumb:{channel}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    thumb_left,
                    track.y - 3.0,
                    3.0,
                    track.height + 6.0,
                ),
                fill=Color(1, 1, 1) if self.enabled else self._disabled_surface,
                corner_radius=CornerRadius.uniform(1.5),
                z_index=4,
                hit_testable=False,
            )
        )
        if channel == self._active_channel:
            root.add(
                SceneNode(
                    key=f"{self.key}:active:{channel}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(
                        track.x - 2.0,
                        track.y - 2.0,
                        track.width + 4.0,
                        track.height + 4.0,
                    ),
                    fill=self._accent_surface.with_alpha(0.08),
                    corner_radius=CornerRadius.uniform(5.0),
                    z_index=1,
                    hit_testable=False,
                )
            )

    def _append_checkerboard(self, root: SceneNode, bounds: Rect, name: str) -> None:
        if bounds.width <= 0 or bounds.height <= 0:
            return
        columns = min(32, max(1, math.ceil(bounds.width / 8)))
        rows = min(8, max(1, math.ceil(bounds.height / 8)))
        width, height = bounds.width / columns, bounds.height / rows
        path = Path2D((Point(0, 0), Point(width, 0),
                       Point(width, height), Point(0, height)))
        for row in range(rows):
            for column in range(columns):
                root.add(SceneNode(
                    key=f"{self.key}:checker:{name}:{row}:{column}",
                    kind=SceneNodeKind.PATH,
                    bounds=Rect(bounds.x + column * width, bounds.y + row * height, width, height),
                    path=path,
                    fill=self._surface if (row + column) % 2 else self._border,
                    z_index=1,
                    hit_testable=False,
                ))

    def _gradient_color(self, channel: ColorChannel, ratio: float) -> Color:
        ratio = _clamp_unit(ratio)
        if channel == "hue":
            red, green, blue = colorsys.hsv_to_rgb(ratio, 1.0, 1.0)
            return Color(float(red), float(green), float(blue), 1.0)
        if channel == "saturation":
            red, green, blue = colorsys.hsv_to_rgb(self._hue, ratio, self._value)
            return Color(float(red), float(green), float(blue), 1.0)
        if channel == "value":
            red, green, blue = colorsys.hsv_to_rgb(self._hue, self._saturation, ratio)
            return Color(float(red), float(green), float(blue), 1.0)
        red, green, blue = colorsys.hsv_to_rgb(self._hue, self._saturation, self._value)
        return Color(float(red), float(green), float(blue), ratio)

    def _channel_text(self, channel: ColorChannel) -> str:
        value = self.channel_value(channel)
        if channel == "hue":
            return f"{round(value * 360.0):d}°"
        return f"{round(value * 100.0):d}%"

    def _accessibility_value(self, channel: ColorChannel) -> float:
        scale = 360.0 if channel == "hue" else 100.0
        return self.channel_value(channel) * scale

    def _publish_change(self, old: Color, *, input_event: Event | None) -> None:
        new = self.value
        self._sync_accessibility()
        if new == old:
            return
        self.invalidate(reason="color")
        self.emit(
            "color_changed",
            old_value=old,
            value=new,
            hex_value=self.hex_value,
            input_event=input_event,
        )

    def _sync_accessibility(self) -> None:
        self.accessible_value_text = self.hex_value

    def _channel_from_y(self, y: float) -> ColorChannel | None:
        for channel in self.channels:
            track = self.track_bounds(channel)
            if track.y - 4.0 <= y <= track.bottom + 4.0:
                return channel
        return None

    def _value_from_x(self, channel: ColorChannel, x: float) -> float:
        track = self.track_bounds(channel)
        if track.width <= 0.0:
            return 0.0
        return _clamp_unit((x - track.x) / track.width)

    def _on_pointer_down(self, event: Event) -> None:
        if event.source is not self or event.default_prevented:
            return
        platform = _platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform is None
            or platform.button is not PointerButton.LEFT
            or platform.x is None
            or platform.y is None
        ):
            return
        channel = self._channel_from_y(platform.y)
        if channel is None:
            return
        self.activate_channel(channel)
        self._drag_channel = channel
        if self.mounted_window is not None:
            self.mounted_window.capture_pointer(self)
        self.set_channel_value(channel, self._value_from_x(channel, platform.x), input_event=event)
        event.prevent_default()

    def _on_pointer_move(self, event: Event) -> None:
        platform = _platform_event(event, PlatformEventKind.POINTER_MOVE)
        if (
            not self.enabled
            or self._drag_channel is None
            or platform is None
            or platform.x is None
        ):
            return
        self.set_channel_value(
            self._drag_channel,
            self._value_from_x(self._drag_channel, platform.x),
            input_event=event,
        )

    def _on_pointer_up(self, event: Event) -> None:
        platform = _platform_event(event, PlatformEventKind.POINTER_UP)
        if platform is None or platform.button is not PointerButton.LEFT:
            return
        if self._drag_channel is not None and platform.x is not None and self.enabled:
            self.set_channel_value(
                self._drag_channel,
                self._value_from_x(self._drag_channel, platform.x),
                input_event=event,
            )
        self._drag_channel = None

    def _on_key_down(self, event: Event) -> None:
        if event.source is not self or event.default_prevented:
            return
        platform = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform is None or platform.ctrl or platform.alt or platform.meta:
            return
        key_code = platform.key_code
        if key_code in {_VK_RETURN, _VK_SPACE}:
            self.emit("activated", value=self.value, hex_value=self.hex_value, input_event=event)
        elif key_code == _VK_UP:
            self._cycle_channel(-1)
        elif key_code == _VK_DOWN:
            self._cycle_channel(1)
        elif key_code == _VK_LEFT:
            self.adjust_active(-1)
        elif key_code == _VK_RIGHT:
            self.adjust_active(1)
        elif key_code == _VK_PRIOR:
            self.adjust_active(1, coarse=True)
        elif key_code == _VK_NEXT:
            self.adjust_active(-1, coarse=True)
        elif key_code == _VK_HOME:
            self.set_channel_value(self._active_channel, 0.0, input_event=event)
        elif key_code == _VK_END:
            self.set_channel_value(self._active_channel, 1.0, input_event=event)
        else:
            return
        event.prevent_default()

    def _cycle_channel(self, amount: int) -> None:
        channels = self.channels
        index = channels.index(self._active_channel)
        self._active_channel = channels[(index + amount) % len(channels)]
        self.invalidate(reason="active_channel")

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        changed = self._focused or self._drag_channel is not None
        self._focused = False
        self._drag_channel = None
        if self.mounted_window is not None:
            self.mounted_window.release_pointer_capture(self)
        if changed:
            self.invalidate(reason="focus_lost")

    def _on_capture_lost(self, _event: Event) -> None:
        self._drag_channel = None


__all__ = ["ColorChannel", "ColorPicker"]
