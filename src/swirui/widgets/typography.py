"""Responsive typography scopes for retained SwirUI component trees."""

from __future__ import annotations

import math
from collections.abc import Iterator

from swirui.core import Component
from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .button import Button
from .input import _TextInputBase
from .responsive import ResponsiveBreakpoints, ResponsiveValue, ViewportClass
from .text import Label

_TypographyTarget = Label | Button | _TextInputBase


def _validate_scale(value: float, *, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero.")
    return normalized


def _normalize_scales(value: ResponsiveValue[float]) -> ResponsiveValue[float]:
    return ResponsiveValue(
        compact=_validate_scale(value.compact, name="compact typography scale"),
        desktop=_validate_scale(value.desktop, name="desktop typography scale"),
        ultrawide=_validate_scale(value.ultrawide, name="ultrawide typography scale"),
    )


class DynamicTypography(Widget):
    """Apply one responsive type scale to an existing retained widget subtree.

    The scope preserves the authored font-size hierarchy and multiplies it by a
    viewport-class scale before descendant layout measurement. This means text,
    buttons and text inputs are measured and rendered at the same effective size
    without replacing retained components or losing focus/input state.

    Scaling is expressed against logical-DIP viewport widths. The renderer keeps
    the existing logical-DIP -> physical-pixel HiDPI boundary, so responsive type
    remains independent from monitor scale. Nested ``DynamicTypography`` scopes
    own their descendants and override an outer scope instead of compounding it.
    """

    def __init__(
        self,
        content: Widget,
        *,
        bounds: Rect,
        scales: ResponsiveValue[float] | None = None,
        breakpoints: ResponsiveBreakpoints | None = None,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._content = content
        self._breakpoints = breakpoints or ResponsiveBreakpoints()
        self._scales = _normalize_scales(
            scales
            or ResponsiveValue(
                compact=0.9,
                desktop=1.0,
                ultrawide=1.1,
            )
        )
        self._fill_viewport = bool(fill_viewport)
        self._current_variant = ViewportClass.COMPACT
        self._current_scale = self._scales.compact
        self._font_baselines: dict[Component, float] = {}
        self._last_applied: dict[Component, float] = {}
        self.add(content)

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
        self.invalidate(reason="dynamic_typography_breakpoints")

    @property
    def scales(self) -> ResponsiveValue[float]:
        return self._scales

    @scales.setter
    def scales(self, value: ResponsiveValue[float]) -> None:
        normalized = _normalize_scales(value)
        if normalized == self._scales:
            return
        self._scales = normalized
        self.invalidate(reason="dynamic_typography_scales")

    @property
    def fill_viewport(self) -> bool:
        return self._fill_viewport

    @fill_viewport.setter
    def fill_viewport(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._fill_viewport:
            return
        self._fill_viewport = normalized
        self.invalidate(reason="dynamic_typography_fill_viewport")

    @property
    def current_variant(self) -> ViewportClass:
        return self._current_variant

    @property
    def current_scale(self) -> float:
        return self._current_scale

    def scale_for_width(self, width: float) -> float:
        """Return the validated responsive typography scale for ``width``."""

        return self.scales.resolve(self.breakpoints.classify(width))

    def measure(self, available: Size | None = None) -> Size:
        available_size = available or self.preferred_size
        self._apply_for_width(available_size.width)
        measured = self.content.measure(available_size)
        natural = Size(
            max(self.preferred_size.width, measured.width),
            max(self.preferred_size.height, measured.height),
        )
        constrained = self.layout_constraints.constrain(natural)
        if available is None:
            return constrained
        return self.layout_constraints.constrain(
            Size(
                min(constrained.width, max(0.0, available.width)),
                min(constrained.height, max(0.0, available.height)),
            )
        )

    def prepare_layout(self, viewport: Rect) -> None:
        if self.fill_viewport:
            self._set_layout_bounds(viewport)
        self._apply_for_width(self.bounds.width)
        self.content._set_layout_bounds(self.bounds)

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

    def _apply_for_width(self, width: float) -> None:
        variant = self.breakpoints.classify(width)
        scale = self.scales.resolve(variant)
        self._current_variant = variant
        self._current_scale = scale
        self._apply_scale(scale)

    def _apply_scale(self, scale: float) -> None:
        active: set[Component] = set()
        for target in self._typography_targets(self.content):
            active.add(target)
            current = float(target._font_size)
            baseline = self._font_baselines.get(target)
            last_applied = self._last_applied.get(target)
            if baseline is None:
                baseline = current
            elif last_applied is not None and not math.isclose(
                current,
                last_applied,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                # A public font-size mutation happened while this scope was active.
                # Treat the newly authored value as the next stable baseline.
                baseline = current
            effective = baseline * scale
            target._font_size = effective
            self._font_baselines[target] = baseline
            self._last_applied[target] = effective

        for stale_target in tuple(self._font_baselines):
            if stale_target in active:
                continue
            stale_target._font_size = self._font_baselines.pop(stale_target)
            self._last_applied.pop(stale_target, None)

    def _typography_targets(self, root: Component) -> Iterator[_TypographyTarget]:
        if isinstance(root, DynamicTypography):
            return
        if isinstance(root, (Label, Button, _TextInputBase)):
            yield root
        for child in root.children:
            yield from self._typography_targets(child)


__all__ = ["DynamicTypography"]
