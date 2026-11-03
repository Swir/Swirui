"""Theme-driven materials and decorative depth around ordinary retained controls."""

from dataclasses import replace

from swirui.core import AccessibilityRole
from swirui.rendering import Color, LinearGradient, Point, Rect, SceneNode
from swirui.surface_style import SurfaceStyle
from swirui.theme import FUTURE_DARK, Theme

from .base import Widget

_DEFAULT_STYLE = SurfaceStyle()


class ThemeSurface(Widget):
    """Container using theme.surface_style or an explicit local style override.

    Decorative planes, shadow and glow do not receive input. Child controls retain
    ordinary layout and hit testing; perspective applies to backplates only.
    """

    def __init__(
        self, *, bounds: Rect, key: str | None = None, theme: Theme | None = None,
        style: SurfaceStyle | None = None, opacity: float = 1, z_index: int = 0,
        accessible_name: str | None = None,
    ) -> None:
        self._validate_style(style)
        self._style = style
        self._interaction_enabled = False
        self._interaction_progress = 0.0
        super().__init__(bounds=bounds, key=key, opacity=opacity, z_index=z_index,
                         accessibility_role=AccessibilityRole.GROUP,
                         accessible_name=accessible_name)
        self._bind_theme(theme, {})

    @staticmethod
    def _validate_style(value: SurfaceStyle | None) -> None:
        if value is not None and not isinstance(value, SurfaceStyle):
            raise TypeError("style must be a SurfaceStyle or None.")

    @property
    def style(self) -> SurfaceStyle | None:
        return self._style

    @style.setter
    def style(self, value: SurfaceStyle | None) -> None:
        self._validate_style(value)
        if self._style != value:
            self._style = value
            self.invalidate(reason="effect")

    @property
    def effective_style(self) -> SurfaceStyle:
        theme = self.effective_theme
        return self.style or (theme.surface_style if theme else None) or _DEFAULT_STYLE

    def build_scene_node(self) -> SceneNode:
        theme = self.effective_theme or FUTURE_DARK
        style = self.effective_style
        progress = self._interaction_progress
        if progress:
            style = replace(
                style, elevation=min(64, style.elevation + 8 * progress),
                glow_radius=max(style.glow_radius, 24 * progress),
                glow_opacity=max(style.glow_opacity, .12 * progress),
                border_opacity=min(1, style.border_opacity + .3 * progress),
            )
        node = style.to_scene_node(self.key, self.bounds, theme)
        # Only the opt-in container receives input; decorative planes never do.
        node.hit_testable = self._interaction_enabled and self.enabled
        if node.hit_testable:
            node.fill = Color(0, 0, 0, 0)
        if progress and self.bounds.width > 8 and self.bounds.height > 8:
            inset = min(theme.control_radius, self.bounds.width / 4, self.bounds.height / 4)
            sheen = LinearGradient.two_color(
                theme.surface_color("accent").with_alpha(.045 * progress),
                theme.surface_color("accent").with_alpha(0),
                start=Point(0, 0), end=Point(1, 1),
            ).to_scene_node(
                f"{self.key}:sheen",
                Rect(self.bounds.x + inset, self.bounds.y + inset,
                     self.bounds.width - 2 * inset, self.bounds.height - 2 * inset),
                steps=32,
            )
            for decoration in sheen.walk():
                decoration.hit_testable = False
            sheen.z_index = -1
            node.add(sheen)
        node.opacity = self.opacity
        node.z_index = self.z_index
        return node
