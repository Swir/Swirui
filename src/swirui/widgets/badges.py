"""Retained badge and selectable chip controls for SwirUI."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole, Event
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import Theme

from .base import ThemeStyle, Widget
from .button import Button

_BADGE_BACKGROUND = Color.from_hex("#113047")
_BADGE_FOREGROUND = Color.from_hex("#C9F5FF")
_CHIP_BACKGROUND = Color.from_hex("#102737")
_CHIP_SELECTED_BACKGROUND = Color.from_hex("#087FCE")
_CHIP_FOREGROUND = Color.from_hex("#CBEFFF")
_CHIP_SELECTED_FOREGROUND = Color.from_hex("#F4FAFF")


class Badge(Widget):
    """Compact non-interactive status pill rendered through retained GPU primitives."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        key: str | None = None,
        theme: Theme | None = None,
        background: Color | None = None,
        foreground: Color | None = None,
        corner_radius: float | None = None,
        font_size: float = 13.0,
        font_family: str | None = None,
        padding: float = 8.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._background = background or _BADGE_BACKGROUND
        self._foreground = foreground or _BADGE_FOREGROUND
        self._corner_radius = self._validate_non_negative(
            10.0 if corner_radius is None else corner_radius, "corner_radius"
        )
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(
            "Segoe UI" if font_family is None else font_family
        )
        self._padding = self._validate_non_negative(padding, "padding")
        self._auto_accessible_name = accessible_name is None
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.TEXT,
            accessible_name=self._text if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )

        self._bind_theme(
            theme,
            {
                "_background": ("surface", "raised", _BADGE_BACKGROUND),
                "_foreground": ("text", "text", _BADGE_FOREGROUND),
                "_font_family": ("token", "font_family", "Segoe UI"),
                "_corner_radius": ("token", "control_radius", 10.0),
            },
            {
                "_background": background,
                "_foreground": foreground,
                "_font_family": self._font_family if font_family is not None else None,
                "_corner_radius": corner_radius,
            },
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
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="text")

    @property
    def background(self) -> Color:
        return self._background

    @background.setter
    def background(self, value: Color) -> None:
        self._theme_overrides["_background"] = value
        if value == self._background:
            return
        self._background = value
        self.invalidate(reason="background")

    @property
    def foreground(self) -> Color:
        return self._foreground

    @foreground.setter
    def foreground(self, value: Color) -> None:
        self._theme_overrides["_foreground"] = value
        if value == self._foreground:
            return
        self._foreground = value
        self.invalidate(reason="foreground")

    def build_scene_node(self) -> SceneNode:
        node = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self.background,
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=False,
        )
        text_bounds = self._content_bounds()
        if self.text and text_bounds.width > 0.0 and text_bounds.height > 0.0:
            node.add(
                SceneNode(
                    key=f"{self.key}:text",
                    kind=SceneNodeKind.TEXT,
                    bounds=text_bounds,
                    fill=self.foreground,
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
        height = min(self.bounds.height, line_height)
        y = self.bounds.y + max(0.0, (self.bounds.height - height) * 0.5)
        return Rect(self.bounds.x + self._padding, y, width, height)

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


class Chip(Button):
    """Keyboard-accessible selectable chip with retained button interaction semantics."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        key: str | None = None,
        theme: Theme | None = None,
        selected: bool = False,
        background: Color | None = None,
        selected_background: Color | None = None,
        foreground: Color | None = None,
        selected_foreground: Color | None = None,
        corner_radius: float | None = None,
        font_size: float = 14.0,
        font_family: str | None = None,
        padding: float = 12.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._selected = bool(selected)
        self._selected_background = selected_background or _CHIP_SELECTED_BACKGROUND
        self._selected_foreground = selected_foreground or _CHIP_SELECTED_FOREGROUND
        super().__init__(
            text,
            theme=theme,
            bounds=bounds,
            key=key,
            background=background,
            foreground=foreground,
            corner_radius=corner_radius,
            font_size=font_size,
            font_family=font_family,
            padding=padding,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._theme_overrides.update(
            {
                key: value
                for key, value in {
                    "_selected_background": selected_background,
                    "_selected_foreground": selected_foreground,
                }.items()
                if value is not None
            }
        )
        self._apply_theme_values(self.effective_theme)
        self.accessibility_role = AccessibilityRole.CHIP
        self.accessible_checked = self._selected
        self.on("click", self._on_click_toggle)

    def _button_theme_styles(self) -> dict[str, ThemeStyle]:
        styles = super()._button_theme_styles()
        styles.update(
            {
                "_background": ("surface", "raised", _CHIP_BACKGROUND),
                "_hover_background": ("surface", "hover", styles["_hover_background"][2]),
                "_pressed_background": ("surface", "pressed", styles["_pressed_background"][2]),
                "_focused_background": ("surface", "hover", styles["_focused_background"][2]),
                "_foreground": ("text", "text", _CHIP_FOREGROUND),
                "_selected_background": ("surface", "accent", _CHIP_SELECTED_BACKGROUND),
                "_selected_foreground": ("text", "on_accent", _CHIP_SELECTED_FOREGROUND),
                "_corner_radius": ("token", "control_radius", 16.0),
            }
        )
        return styles

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._set_selected(bool(value), input_event=None)

    def build_scene_node(self) -> SceneNode:
        node = super().build_scene_node()
        if self.selected and self.enabled:
            for child in node.children:
                if child.key == f"{self.key}:content":
                    child.fill = self._selected_foreground
        return node

    def _current_background(self) -> Color:
        if self.enabled and self.selected and self._theme:
            if "_selected_background" in self._theme_overrides:
                return self._selected_background
            if self.pressed:
                return self._theme.surface_color("accent_pressed")
            if self.hovered or self.focused:
                return self._theme.surface_color("accent_hover")
            return self._selected_background
        if (
            self.enabled
            and self.selected
            and not self.pressed
            and not self.hovered
            and not self.focused
        ):
            return self._selected_background
        return super()._current_background()

    def _set_selected(self, value: bool, *, input_event: object | None) -> None:
        if value == self._selected:
            return
        self._selected = value
        self.accessible_checked = value
        self.invalidate(reason="selected")
        self.emit("selection_changed", selected=value, input_event=input_event)

    def _on_click_toggle(self, event: Event) -> None:
        self._set_selected(
            not self.selected,
            input_event=event.data.get("input_event"),
        )
