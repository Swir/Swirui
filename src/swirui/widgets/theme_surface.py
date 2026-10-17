"""Theme-driven materials and decorative depth around ordinary retained controls."""

from swirui.core import AccessibilityRole
from swirui.rendering import Rect, SceneNode
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
        node = self.effective_style.to_scene_node(
            self.key, self.bounds, self.effective_theme or FUTURE_DARK,
        )
        node.opacity = self.opacity
        node.z_index = self.z_index
        return node
