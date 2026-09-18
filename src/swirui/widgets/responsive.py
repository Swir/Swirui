"""Responsive retained layout primitives for SwirUI."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from swirui.rendering.geometry import Rect, Size

from .layout import (
    CrossAxisAlignment,
    Insets,
    MainAxisAlignment,
    _LinearLayout,
)

_T = TypeVar("_T")


class ViewportClass(StrEnum):
    """Named responsive width classes used by retained layouts."""

    COMPACT = "compact"
    DESKTOP = "desktop"
    ULTRAWIDE = "ultrawide"


class LayoutDirection(StrEnum):
    """Primary child flow direction for a responsive layout variant."""

    ROW = "row"
    COLUMN = "column"


@dataclass(frozen=True, slots=True)
class ResponsiveBreakpoints:
    """Deterministic logical-DIP thresholds for responsive width classes."""

    compact_max: float = 720.0
    ultrawide_min: float = 1440.0

    def __post_init__(self) -> None:
        compact = float(self.compact_max)
        ultrawide = float(self.ultrawide_min)
        if not math.isfinite(compact) or compact <= 0.0:
            raise ValueError("compact_max must be finite and greater than zero.")
        if not math.isfinite(ultrawide) or ultrawide <= compact:
            raise ValueError("ultrawide_min must be finite and greater than compact_max.")
        object.__setattr__(self, "compact_max", compact)
        object.__setattr__(self, "ultrawide_min", ultrawide)

    def classify(self, width: float) -> ViewportClass:
        """Classify a logical-DIP viewport width."""

        normalized = float(width)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError("Viewport width must be finite and non-negative.")
        if normalized < self.compact_max:
            return ViewportClass.COMPACT
        if normalized < self.ultrawide_min:
            return ViewportClass.DESKTOP
        return ViewportClass.ULTRAWIDE


@dataclass(frozen=True, slots=True)
class ResponsiveValue(Generic[_T]):
    """Resolve one explicit value for each standard responsive width class."""

    compact: _T
    desktop: _T
    ultrawide: _T

    def resolve(self, viewport_class: ViewportClass) -> _T:
        resolved = ViewportClass(viewport_class)
        if resolved is ViewportClass.COMPACT:
            return self.compact
        if resolved is ViewportClass.DESKTOP:
            return self.desktop
        return self.ultrawide

    def resolve_width(
        self,
        width: float,
        *,
        breakpoints: ResponsiveBreakpoints | None = None,
    ) -> _T:
        policy = breakpoints or ResponsiveBreakpoints()
        return self.resolve(policy.classify(width))


@dataclass(frozen=True, slots=True)
class ResponsiveLayoutSpec:
    """Layout behavior selected for one responsive viewport class."""

    direction: LayoutDirection = LayoutDirection.COLUMN
    spacing: float = 0.0
    padding: Insets | float = 0.0
    main_alignment: MainAxisAlignment = MainAxisAlignment.START
    cross_alignment: CrossAxisAlignment = CrossAxisAlignment.START
    max_content_width: float | None = None

    def __post_init__(self) -> None:
        direction = LayoutDirection(self.direction)
        spacing = float(self.spacing)
        padding = self.padding if isinstance(self.padding, Insets) else Insets.all(self.padding)
        main_alignment = MainAxisAlignment(self.main_alignment)
        cross_alignment = CrossAxisAlignment(self.cross_alignment)
        if not math.isfinite(spacing) or spacing < 0.0:
            raise ValueError("spacing must be a finite non-negative value.")

        max_content_width = self.max_content_width
        if max_content_width is not None:
            max_content_width = float(max_content_width)
            if not math.isfinite(max_content_width) or max_content_width <= 0.0:
                raise ValueError("max_content_width must be finite and greater than zero.")

        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "spacing", spacing)
        object.__setattr__(self, "padding", padding)
        object.__setattr__(self, "main_alignment", main_alignment)
        object.__setattr__(self, "cross_alignment", cross_alignment)
        object.__setattr__(self, "max_content_width", max_content_width)


class ResponsiveLayout(_LinearLayout):
    """Arrange one retained child tree differently across responsive breakpoints.

    SwirUI keeps a single component tree and switches layout policy, rather than
    duplicating whole trees for compact/desktop/ultrawide modes. This preserves
    component identity, focus state and routed input while window resizes trigger
    ordinary retained SceneGraph rebuilds.
    """

    _horizontal = False

    def __init__(
        self,
        *,
        bounds: Rect,
        compact: ResponsiveLayoutSpec,
        desktop: ResponsiveLayoutSpec | None = None,
        ultrawide: ResponsiveLayoutSpec | None = None,
        breakpoints: ResponsiveBreakpoints | None = None,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        self._breakpoints = breakpoints or ResponsiveBreakpoints()
        desktop_spec = desktop or compact
        ultrawide_spec = ultrawide or desktop_spec
        self._specs = {
            ViewportClass.COMPACT: compact,
            ViewportClass.DESKTOP: desktop_spec,
            ViewportClass.ULTRAWIDE: ultrawide_spec,
        }
        self._current_variant = ViewportClass.COMPACT
        self._active_content_max_width: float | None = None
        initial = self._specs[self._current_variant]
        super().__init__(
            bounds=bounds,
            spacing=initial.spacing,
            padding=initial.padding,
            main_alignment=initial.main_alignment,
            cross_alignment=initial.cross_alignment,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._apply_spec(initial, self._current_variant)

    @property
    def breakpoints(self) -> ResponsiveBreakpoints:
        return self._breakpoints

    @breakpoints.setter
    def breakpoints(self, value: ResponsiveBreakpoints) -> None:
        if value == self._breakpoints:
            return
        self._breakpoints = value
        self.invalidate(reason="responsive_breakpoints")

    @property
    def current_variant(self) -> ViewportClass:
        return self._current_variant

    def variant_spec(self, viewport_class: ViewportClass) -> ResponsiveLayoutSpec:
        return self._specs[ViewportClass(viewport_class)]

    def set_variant_spec(
        self,
        viewport_class: ViewportClass,
        spec: ResponsiveLayoutSpec,
    ) -> ResponsiveLayout:
        resolved = ViewportClass(viewport_class)
        if self._specs[resolved] == spec:
            return self
        self._specs[resolved] = spec
        self.invalidate(reason="responsive_variant")
        return self

    def measure(self, available: Size | None = None) -> Size:
        width = self.preferred_size.width if available is None else available.width
        self._apply_for_width(width)
        return super().measure(available)

    def prepare_layout(self, viewport: Rect) -> None:
        self._apply_for_width(viewport.width)
        super().prepare_layout(viewport)

    def _apply_for_width(self, width: float) -> None:
        variant = self.breakpoints.classify(width)
        self._apply_spec(self._specs[variant], variant)

    def _apply_spec(
        self,
        spec: ResponsiveLayoutSpec,
        variant: ViewportClass,
    ) -> None:
        self._current_variant = variant
        self._horizontal = spec.direction is LayoutDirection.ROW
        self._spacing = spec.spacing
        self._padding = (
            spec.padding if isinstance(spec.padding, Insets) else Insets.all(spec.padding)
        )
        self._main_alignment = spec.main_alignment
        self._cross_alignment = spec.cross_alignment
        self._active_content_max_width = spec.max_content_width

    def _content_bounds(self) -> Rect:
        content = super()._content_bounds()
        maximum = self._active_content_max_width
        if maximum is None or content.width <= maximum:
            return content
        return Rect(
            content.x + ((content.width - maximum) / 2.0),
            content.y,
            maximum,
            content.height,
        )


__all__ = [
    "LayoutDirection",
    "ResponsiveBreakpoints",
    "ResponsiveLayout",
    "ResponsiveLayoutSpec",
    "ResponsiveValue",
    "ViewportClass",
]
