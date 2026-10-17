"""Elapsed-time theme transitions with linear-light palette interpolation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from typing import cast

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering.geometry import Color
from .theme import ColorRole, Palette, Theme

_ROLES = tuple(cast(ColorRole, item.name) for item in fields(Palette))
_TEXT_BACKGROUNDS = {
    "text": ("canvas", "surface", "raised", "hover", "pressed", "selection"),
    "muted": ("canvas", "surface", "raised"),
    "on_accent": ("accent", "accent_hover", "accent_pressed"),
    "success": ("surface", "raised"),
    "warning": ("surface", "raised"),
    "error": ("surface", "raised"),
}


def _encoded(value: float) -> int:
    channel = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
    return round(min(1.0, max(0.0, channel)) * 255)


def _swatch(color: Color) -> str:
    values = (_encoded(color.r), _encoded(color.g), _encoded(color.b), round(color.a * 255))
    return "#" + "".join(f"{value:02X}" for value in values[:3 if values[3] == 255 else 4])


def _mix(first: Color, second: Color, progress: float) -> Color:
    alpha = (1 - progress) * first.a + progress * second.a
    if alpha == 0:
        return Color(0, 0, 0, 0)
    channels = [
        ((1 - progress) * a * first.a + progress * b * second.a) / alpha
        for a, b in zip((first.r, first.g, first.b), (second.r, second.g, second.b), strict=True)
    ]
    return Color(channels[0], channels[1], channels[2], alpha)


def _contrast(first: Color, second: Color) -> float:
    def luminance(color: Color) -> float:
        return 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b
    a, b = luminance(first), luminance(second)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


class ThemeTransition:
    """Interpolate palette/radius; switch font families at completion.

    RGB is blended in premultiplied linear light, then encoded to palette HEX.
    Endpoints are the exact authored Theme objects. Either endpoint requesting
    reduced motion makes the transition immediate. By default, opaque text
    roles with poor intermediate contrast use the best of endpoint/black/white
    foregrounds. Arbitrary custom palettes cannot guarantee a universal ratio.
    """

    def __init__(
        self, from_value: Theme, to_value: Theme, duration: float,
        update: Callable[[Theme], None], *, easing: Easing = ease_in_out_cubic,
        protect_text_contrast: bool = True, on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.from_value, self.to_value = from_value, to_value
        self.update = update
        self.protect_text_contrast = protect_text_contrast
        self._source = {role: from_value.surface_color(role) for role in _ROLES}
        self._target = {role: to_value.surface_color(role) for role in _ROLES}
        # Validate duration even when reduced motion will make it instantaneous.
        self._tween = Tween(0, 1, duration, self._publish, easing=easing, on_complete=on_complete)
        if from_value.reduced_motion or to_value.reduced_motion:
            self._tween.duration = 0

    @property
    def status(self) -> AnimationStatus:
        return self._tween.status

    @property
    def elapsed(self) -> float:
        return self._tween.elapsed

    @property
    def progress(self) -> float:
        return self._tween.progress

    def start(self) -> ThemeTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def _publish(self, progress: float) -> None:
        if progress <= 0:
            self.update(self.from_value)
            return
        if progress >= 1:
            self.update(self.to_value)
            return
        colors = {role: _mix(self._source[role], self._target[role], progress) for role in _ROLES}
        if self.protect_text_contrast:
            for name, backgrounds in _TEXT_BACKGROUNDS.items():
                role = cast(ColorRole, name)
                surfaces = [colors[cast(ColorRole, bg)] for bg in backgrounds]
                if colors[role].a != 1 or any(bg.a != 1 for bg in surfaces):
                    continue

                def score(color: Color, surfaces: list[Color] = surfaces) -> float:
                    return min(_contrast(color, bg) for bg in surfaces)

                if score(colors[role]) < 4.5:
                    candidates = [colors[role], self._source[role], self._target[role],
                                  Color(0, 0, 0), Color(1, 1, 1)]
                    colors[role] = max((c for c in candidates if c.a == 1), key=score)
        palette = Palette(**{role: _swatch(color) for role, color in colors.items()})
        radius = ((1 - progress) * self.from_value.control_radius
                  + progress * self.to_value.control_radius)
        self.update(replace(self.from_value, palette=palette, control_radius=radius,
                            motion_duration=self.to_value.motion_duration))
