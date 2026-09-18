"""GPU-backed retained text widgets."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Color, Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .measurement import measure_text_block


class Label(Widget):
    """Non-interactive retained text rendered by the native shaped-text path."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        key: str | None = None,
        color: Color | None = None,
        font_size: float = 16.0,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._color = color or Color(1.0, 1.0, 1.0, 1.0)
        self._font_size = self._validate_font_size(font_size)
        self._font_family = self._validate_font_family(font_family)
        self._auto_accessible_name = accessible_name is None
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
            accessibility_role=AccessibilityRole.TEXT,
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

    @property
    def color(self) -> Color:
        return self._color

    @color.setter
    def color(self, value: Color) -> None:
        if value == self._color:
            return
        self._color = value
        self.invalidate(reason="color")

    @property
    def font_size(self) -> float:
        return self._font_size

    @font_size.setter
    def font_size(self, value: float) -> None:
        normalized = self._validate_font_size(value)
        if normalized == self._font_size:
            return
        self._font_size = normalized
        self.invalidate(reason="font_size")

    @property
    def font_family(self) -> str:
        return self._font_family

    @font_family.setter
    def font_family(self, value: str) -> None:
        normalized = self._validate_font_family(value)
        if normalized == self._font_family:
            return
        self._font_family = normalized
        self.invalidate(reason="font_family")

    def intrinsic_size(self, available: Size | None = None) -> Size:
        """Measure text content while preserving an explicitly authored baseline."""

        measured = measure_text_block(
            self.text,
            font_size=self.font_size,
            available_width=None if available is None else available.width,
        )
        return Size(
            max(self.preferred_size.width, measured.width),
            max(self.preferred_size.height, measured.height),
        )

    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.TEXT,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self.color,
            text=self.text,
            font_size=self.font_size,
            font_family=self.font_family,
            clip_to_bounds=self.clip_to_bounds,
            hit_testable=False,
        )

    @staticmethod
    def _validate_font_size(value: float) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError("font_size must be finite and greater than zero.")
        return normalized

    @staticmethod
    def _validate_font_family(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("font_family cannot be empty.")
        return normalized


class Text(Label):
    """Public semantic alias for Label with the same retained text behavior."""
