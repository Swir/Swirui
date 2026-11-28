"""GPU-backed retained text widgets."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, NamedTuple

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Color, Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import Theme

from .base import Widget
from .measurement import measure_text_block

if TYPE_CHECKING:
    from swirui.rendering.text_layout import TextShaper
    from swirui.window import Window


class _FittedLine(NamedTuple):
    size: float
    width: float


class Label(Widget):
    """Non-interactive retained text rendered by the native shaped-text path."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        key: str | None = None,
        theme: Theme | None = None,
        color: Color | None = None,
        font_size: float = 16.0,
        min_font_size: float | None = None,
        font_family: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._color = color or (theme.text_color("text") if theme else Color(1.0, 1.0, 1.0, 1.0))
        self._font_size = self._validate_font_size(font_size)
        self._min_font_size = None if min_font_size is None else self._validate_font_size(
            min_font_size
        )
        self._fit_key: tuple[object, ...] | None = None
        self._fit_result: _FittedLine | None = None
        self._font_family = self._validate_font_family(
            font_family if font_family is not None else (theme.font_family if theme else "Segoe UI")
        )
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
        self._bind_theme(
            theme,
            {
                "_color": ("text", "text", Color(1, 1, 1, 1)),
                "_font_family": ("token", "font_family", "Segoe UI"),
            },
            {
                "_color": color,
                "_font_family": self._font_family if font_family is not None else None,
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
        self._fit_key = self._fit_result = None
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="text")

    @property
    def color(self) -> Color:
        return self._color

    @color.setter
    def color(self, value: Color) -> None:
        self._theme_overrides["_color"] = value
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
    def min_font_size(self) -> float | None:
        """Smallest size to use when fitting a single line. None keeps the authored size."""
        return self._min_font_size

    @min_font_size.setter
    def min_font_size(self, value: float | None) -> None:
        floor = None if value is None else self._validate_font_size(value)
        if floor != self._min_font_size:
            self._min_font_size = floor
            self._fit_key = self._fit_result = None
            self.invalidate(reason="min_font_size")

    @property
    def font_family(self) -> str:
        return self._font_family

    @font_family.setter
    def font_family(self, value: str) -> None:
        normalized = self._validate_font_family(value)
        self._theme_overrides["_font_family"] = normalized
        if normalized == self._font_family:
            return
        self._font_family = normalized
        self.invalidate(reason="font_family")

    def intrinsic_size(self, available: Size | None = None) -> Size:
        """Measure text content while preserving an explicitly authored baseline."""

        width = available.width if available is not None else None
        fit = self._fit_line(width) if width is not None else None
        if fit is not None and width is not None and fit.width <= width:
            measured = Size(fit.width, fit.size * 1.25)
        else:
            measured = measure_text_block(
                self.text, font_size=fit.size if fit else self.font_size, available_width=width
            )
        return Size(
            max(self.preferred_size.width, measured.width),
            max(self.preferred_size.height, measured.height),
        )

    def _fit_line(self, width: float) -> _FittedLine | None:
        """Measure a single-line caption once per width, font and device scale."""
        if self.min_font_size is None or not self.text:
            return None
        window = self.mounted_window
        shaper = window._text_shaper if window else None
        scale = window.scale if window else 1.0
        key = (self.text, self.font_family, self.font_size, self.min_font_size,
               width, scale, shaper)
        if key != self._fit_key:
            self._fit_result = None
            if self.text.splitlines() == [self.text]:
                self._fit_result = self._measure_fitted_line(
                    width, self.min_font_size, scale, shaper
                )
            self._fit_key = key
        return self._fit_result

    def _measure_fitted_line(self, width: float, floor: float, scale: float,
                             shaper: TextShaper | None) -> _FittedLine:
        def measure(size: float) -> _FittedLine:
            if shaper is not None:
                try:
                    layout = shaper.shape_line(self.text, size, self.font_family, scale)
                    return _FittedLine(size, layout.width)
                except ValueError:
                    # Keep layout available beyond the native shaper's text and font limits.
                    pass
            estimated = measure_text_block(self.text, font_size=size, wrap=False)
            return _FittedLine(size, estimated.width)

        preferred = measure(self.font_size)
        if preferred.width <= width or floor >= self.font_size:
            return preferred
        best = measure(floor)
        if best.width > width:
            return best
        low, high = math.floor(floor) + 1, math.ceil(self.font_size) - 1
        while low <= high:
            size = (low + high) // 2
            candidate = measure(size)
            if candidate.width <= width:
                best = candidate
                low = size + 1
            else:
                high = size - 1
        return best

    def on_unmount(self, window: Window) -> None:
        self._fit_key = self._fit_result = None
        super().on_unmount(window)

    def build_scene_node(self) -> SceneNode:
        fit = self._fit_line(self.bounds.width)
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.TEXT,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self.color,
            text=self.text,
            font_size=fit.size if fit else self.font_size,
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
