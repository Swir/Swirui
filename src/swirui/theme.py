"""Immutable semantic styling shared by native retained widgets.

Themes are explicit per widget: separate windows can use different themes without
process-wide state. Existing explicit color overrides continue to take priority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from .rendering.geometry import Color
from .surface_style import SurfaceStyle

ColorRole = Literal[
    "canvas",
    "surface",
    "raised",
    "hover",
    "pressed",
    "border",
    "focus",
    "accent",
    "accent_hover",
    "accent_pressed",
    "on_accent",
    "text",
    "muted",
    "disabled",
    "disabled_text",
    "selection",
    "success",
    "warning",
    "error",
]


class ButtonVariant(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    GHOST = "ghost"


@dataclass(frozen=True, slots=True)
class Palette:
    """Authored sRGB swatches for the Midnight visual system."""

    canvas: str = "#0C0D12"
    surface: str = "#15171F"
    raised: str = "#1D202B"
    hover: str = "#292D3D"
    pressed: str = "#353B50"
    border: str = "#34394B"
    focus: str = "#BEACFF"
    accent: str = "#B6A0FF"
    accent_hover: str = "#C8B8FF"
    accent_pressed: str = "#9A7FE5"
    on_accent: str = "#171125"
    text: str = "#F3F1FA"
    muted: str = "#A4A8BB"
    disabled: str = "#222530"
    disabled_text: str = "#777D91"
    selection: str = "#514274"
    success: str = "#89E3C1"
    warning: str = "#F4CF86"
    error: str = "#FF99AC"

    def __post_init__(self) -> None:
        for item in fields(self):
            Color.from_hex(getattr(self, item.name))


@lru_cache(maxsize=256)
def _swatch(value: str, linear: bool) -> Color:
    color = Color.from_hex(value)
    if not linear:
        return color

    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return Color(channel(color.r), channel(color.g), channel(color.b), color.a)


@dataclass(frozen=True, slots=True)
class Theme:
    """Shared color, typography, geometry and motion choices.

    ``surface_color`` supplies linear channels for the native GPU shape pipeline;
    ``text_color`` supplies encoded sRGB for native shaped text. This distinction
    keeps a swatch visually consistent across text, controls and raster images.
    The theme does not change the historical ``Color.from_hex`` contract.
    """

    palette: Palette = field(default_factory=Palette)
    font_family: str = "Segoe UI"
    control_radius: float = 12.0
    motion_duration: float = 0.16
    reduced_motion: bool = False
    monospace_family: str = "Cascadia Mono"
    surface_style: SurfaceStyle | None = None

    def __post_init__(self) -> None:
        if self.surface_style is not None and not isinstance(self.surface_style, SurfaceStyle):
            raise TypeError("Theme surface_style must be a SurfaceStyle or None.")
        if not self.font_family.strip():
            raise ValueError("Theme font_family cannot be empty.")
        if not self.monospace_family.strip():
            raise ValueError("Theme monospace_family cannot be empty.")
        for name in ("control_radius", "motion_duration"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Theme {name} must be finite and non-negative.")

    def surface_color(self, role: ColorRole) -> Color:
        return _swatch(getattr(self.palette, role), True)

    def text_color(self, role: ColorRole) -> Color:
        return _swatch(getattr(self.palette, role), False)


DEFAULT_THEME = Theme()
FUTURE_DARK = DEFAULT_THEME
FUTURE_LIGHT = Theme(
    palette=Palette(
        canvas="#F4F5FA",
        surface="#FFFFFF",
        raised="#E9EBF3",
        hover="#DFE2EE",
        pressed="#D2D6E6",
        border="#BDC3D6",
        focus="#6D45CE",
        accent="#7049D3",
        accent_hover="#8059E3",
        accent_pressed="#5734B2",
        on_accent="#FFFFFF",
        text="#171B2A",
        muted="#596176",
        disabled="#E2E5EE",
        disabled_text="#7C8497",
        selection="#D4C6F3",
        success="#146F52",
        warning="#8A5900",
        error="#BC304D",
    )
)
