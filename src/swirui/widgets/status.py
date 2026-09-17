"""Retained badge and chip widgets."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .button import Button

_BADGE_BACKGROUND = Color.from_hex("#103047")
_BADGE_FOREGROUND = Color.from_hex("#62E5FF")
_CHIP_BACKGROUND = Color.from_hex("#163646")
_CHIP_HOVER = Color.from_hex("#1D4B60")
_CHIP_PRESSED = Color.from_hex("#0E2A38")
_CHIP_FOCUSED = Color.from_hex("#205975")
_CHIP_DISABLED = Color.from_hex("#303A40")
_CHIP_FOREGROUND = Color.from_hex("#E9F8FF")


class Badge(Widget):
    """Compact non-interactive status label rendered by the retained GPU path."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        key: str | None = None,
        background: Color | None = None,
        foreground: Color | None = None,
        corner_radius: float | None = None,
        font_size: float = 13.0,
        font_family: str = "Segoe UI",
        padding: float = 8.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._background = background or _BADGE_BACKGROUND
        self._foreground = foreground or _BADGE_FOREGROUND
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        default_radius = min(bounds.height / 2.0, 999.0)
        self._corner_radius = self._validate_non_negative(
            default_radius if corner_radius is None else corner_radius,
            "corner_radius",
        )
        self._auto_accessible_name = accessible_name is None
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=False,
            accessibility_role=AccessibilityRole.STATUS,
            accessible_name=self._text if accessible_name is None else accessible_name,
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
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="text")

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
            hit_testable=False,
        )
        content_width = max(0.0, self.bounds.width - 2.0 * self._padding)
        if self.text and content_width > 0.0 and self.bounds.height > 0.0:
            line_height = min(self.bounds.height, self._font_size * 1.25)
            root.add(
                SceneNode(
                    key=f"{self.key}:content",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        self.bounds.x + self._padding,
                        self.bounds.y + max(0.0, (self.bounds.height - line_height) / 2.0),
                        content_width,
                        line_height,
                    ),
                    fill=self._foreground,
                    text=self.text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        return root

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
    """Compact focusable action chip using the retained Button interaction model."""

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
        font_size: float = 14.0,
        font_family: str = "Segoe UI",
        padding: float = 10.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            text,
            bounds=bounds,
            key=key,
            background=background or _CHIP_BACKGROUND,
            hover_background=hover_background or _CHIP_HOVER,
            pressed_background=pressed_background or _CHIP_PRESSED,
            focused_background=focused_background or _CHIP_FOCUSED,
            disabled_background=disabled_background or _CHIP_DISABLED,
            foreground=foreground or _CHIP_FOREGROUND,
            corner_radius=min(bounds.height / 2.0, 999.0),
            font_size=font_size,
            font_family=font_family,
            padding=padding,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
