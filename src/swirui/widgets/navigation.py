"""Adaptive retained navigation layouts for SwirUI."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .layout import Insets
from .responsive import ResponsiveBreakpoints, ViewportClass


class NavigationMode(StrEnum):
    """Responsive navigation placement modes."""

    BOTTOM = "bottom"
    RAIL = "rail"
    SIDEBAR = "sidebar"


@dataclass(frozen=True, slots=True)
class AdaptiveNavigationSpec:
    """Placement and logical-DIP sizing for one navigation viewport class."""

    mode: NavigationMode
    navigation_extent: float
    gap: float = 0.0

    def __post_init__(self) -> None:
        mode = NavigationMode(self.mode)
        extent = float(self.navigation_extent)
        gap = float(self.gap)
        if not math.isfinite(extent) or extent <= 0.0:
            raise ValueError("navigation_extent must be finite and greater than zero.")
        if not math.isfinite(gap) or gap < 0.0:
            raise ValueError("gap must be a finite non-negative value.")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "navigation_extent", extent)
        object.__setattr__(self, "gap", gap)


class AdaptiveNavigation(Widget):
    """Keep one navigation/content tree while placement adapts to window width.

    Compact widths use a bottom navigation region, desktop widths use a narrow
    left rail, and ultrawide widths use an expanded left sidebar by default.
    All geometry is expressed in logical DIPs, so the existing HiDPI boundary
    and retained GPU scene remain unchanged.
    """

    def __init__(
        self,
        navigation: Widget,
        content: Widget,
        *,
        bounds: Rect,
        breakpoints: ResponsiveBreakpoints | None = None,
        compact: AdaptiveNavigationSpec | None = None,
        desktop: AdaptiveNavigationSpec | None = None,
        ultrawide: AdaptiveNavigationSpec | None = None,
        padding: Insets | float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = True,
    ) -> None:
        super().__init__(
            bounds=bounds,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        if navigation is content:
            raise ValueError("navigation and content must be different widgets.")
        self._navigation = navigation
        self._content = content
        self._breakpoints = breakpoints or ResponsiveBreakpoints()
        self._padding = padding if isinstance(padding, Insets) else Insets.all(padding)
        self._fill_viewport = bool(fill_viewport)
        self._specs = {
            ViewportClass.COMPACT: compact
            or AdaptiveNavigationSpec(NavigationMode.BOTTOM, 64.0, 0.0),
            ViewportClass.DESKTOP: desktop
            or AdaptiveNavigationSpec(NavigationMode.RAIL, 80.0, 0.0),
            ViewportClass.ULTRAWIDE: ultrawide
            or AdaptiveNavigationSpec(NavigationMode.SIDEBAR, 280.0, 0.0),
        }
        self._current_variant = ViewportClass.COMPACT
        self.add(navigation, content)

    @property
    def navigation(self) -> Widget:
        return self._navigation

    @property
    def content(self) -> Widget:
        return self._content

    @property
    def breakpoints(self) -> ResponsiveBreakpoints:
        return self._breakpoints

    @breakpoints.setter
    def breakpoints(self, value: ResponsiveBreakpoints) -> None:
        if value == self._breakpoints:
            return
        self._breakpoints = value
        self.invalidate(reason="adaptive_navigation_breakpoints")

    @property
    def padding(self) -> Insets:
        return self._padding

    @padding.setter
    def padding(self, value: Insets | float) -> None:
        normalized = value if isinstance(value, Insets) else Insets.all(value)
        if normalized == self._padding:
            return
        self._padding = normalized
        self.invalidate(reason="adaptive_navigation_padding")

    @property
    def fill_viewport(self) -> bool:
        return self._fill_viewport

    @fill_viewport.setter
    def fill_viewport(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._fill_viewport:
            return
        self._fill_viewport = normalized
        self.invalidate(reason="adaptive_navigation_fill_viewport")

    @property
    def current_variant(self) -> ViewportClass:
        return self._current_variant

    @property
    def current_spec(self) -> AdaptiveNavigationSpec:
        return self._specs[self._current_variant]

    def variant_spec(self, viewport_class: ViewportClass) -> AdaptiveNavigationSpec:
        return self._specs[ViewportClass(viewport_class)]

    def set_variant_spec(
        self,
        viewport_class: ViewportClass,
        spec: AdaptiveNavigationSpec,
    ) -> AdaptiveNavigation:
        resolved = ViewportClass(viewport_class)
        if self._specs[resolved] == spec:
            return self
        self._specs[resolved] = spec
        self.invalidate(reason="adaptive_navigation_variant")
        return self

    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=self.clip_to_bounds,
            hit_testable=False,
        )

    def measure(self, available: Size | None = None) -> Size:
        available_size = available or self.preferred_size
        variant = self.breakpoints.classify(available_size.width)
        spec = self._specs[variant]
        inner_available = self._inner_size(available_size)
        nav_size = self.navigation.measure(inner_available)
        content_size = self.content.measure(inner_available)

        if spec.mode is NavigationMode.BOTTOM:
            natural = Size(
                max(nav_size.width, content_size.width),
                content_size.height + spec.gap + spec.navigation_extent,
            )
        else:
            natural = Size(
                spec.navigation_extent + spec.gap + content_size.width,
                max(nav_size.height, content_size.height),
            )
        padded = Size(
            natural.width + self.padding.left + self.padding.right,
            natural.height + self.padding.top + self.padding.bottom,
        )
        return self.layout_constraints.constrain(
            Size(
                min(padded.width, available_size.width),
                min(padded.height, available_size.height),
            )
        )

    def prepare_layout(self, viewport: Rect) -> None:
        if self.fill_viewport:
            self._set_layout_bounds(viewport)

        self._current_variant = self.breakpoints.classify(self.bounds.width)
        spec = self.current_spec
        content = self._content_bounds()
        if spec.mode is NavigationMode.BOTTOM:
            nav_height = min(spec.navigation_extent, content.height)
            gap = min(spec.gap, max(0.0, content.height - nav_height))
            body_height = max(0.0, content.height - nav_height - gap)
            self.content._set_layout_bounds(
                Rect(content.x, content.y, content.width, body_height)
            )
            self.navigation._set_layout_bounds(
                Rect(
                    content.x,
                    content.y + body_height + gap,
                    content.width,
                    nav_height,
                )
            )
            return

        nav_width = min(spec.navigation_extent, content.width)
        gap = min(spec.gap, max(0.0, content.width - nav_width))
        body_width = max(0.0, content.width - nav_width - gap)
        self.navigation._set_layout_bounds(
            Rect(content.x, content.y, nav_width, content.height)
        )
        self.content._set_layout_bounds(
            Rect(content.x + nav_width + gap, content.y, body_width, content.height)
        )

    def _inner_size(self, size: Size) -> Size:
        return Size(
            max(0.0, size.width - self.padding.left - self.padding.right),
            max(0.0, size.height - self.padding.top - self.padding.bottom),
        )

    def _content_bounds(self) -> Rect:
        return Rect(
            self.bounds.x + self.padding.left,
            self.bounds.y + self.padding.top,
            max(0.0, self.bounds.width - self.padding.left - self.padding.right),
            max(0.0, self.bounds.height - self.padding.top - self.padding.bottom),
        )


__all__ = [
    "AdaptiveNavigation",
    "AdaptiveNavigationSpec",
    "NavigationMode",
]
