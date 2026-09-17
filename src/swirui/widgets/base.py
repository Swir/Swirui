"""Retained visual widget foundation for SwirUI."""

from __future__ import annotations

import math
from dataclasses import dataclass

from swirui.core import AccessibilityRole, Component
from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode


@dataclass(frozen=True, slots=True)
class LayoutConstraints:
    """Min/max logical-DIP size constraints shared by retained layouts."""

    min_width: float = 0.0
    min_height: float = 0.0
    max_width: float = math.inf
    max_height: float = math.inf

    def __post_init__(self) -> None:
        values = (self.min_width, self.min_height, self.max_width, self.max_height)
        if any(math.isnan(value) or value < 0.0 for value in values):
            raise ValueError("Layout constraints must be non-negative and not NaN.")
        if self.min_width > self.max_width or self.min_height > self.max_height:
            raise ValueError("Minimum layout constraints cannot exceed maximum constraints.")

    def constrain(self, size: Size) -> Size:
        return Size(
            min(max(size.width, self.min_width), self.max_width),
            min(max(size.height, self.min_height), self.max_height),
        )


class Widget(Component):
    """Base component with retained visual geometry.

    Widgets author logical-DIP geometry and compile it to backend-neutral
    :class:`~swirui.rendering.scene.SceneNode` objects. The existing renderer
    pipeline remains responsible for HiDPI conversion and native GPU submission.

    ``layout_constraints`` and ``layout_grow`` are intentionally backend-neutral.
    Layout containers may arrange ``bounds`` during scene preparation without
    emitting a second invalidation from inside the same retained rebuild.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
        focusable: bool = False,
        accessibility_role: AccessibilityRole = AccessibilityRole.GENERIC,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            name,
            key=key,
            focusable=focusable,
            accessibility_role=accessibility_role,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._bounds = bounds
        self._opacity = self._validate_opacity(opacity)
        self._z_index = int(z_index)
        self._clip_to_bounds = bool(clip_to_bounds)
        self._layout_constraints = LayoutConstraints()
        self._layout_grow = 0.0

    @property
    def bounds(self) -> Rect:
        return self._bounds

    @bounds.setter
    def bounds(self, value: Rect) -> None:
        if value == self._bounds:
            return
        self._bounds = value
        self.invalidate(reason="bounds")

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        normalized = self._validate_opacity(value)
        if normalized == self._opacity:
            return
        self._opacity = normalized
        self.invalidate(reason="opacity")

    @property
    def z_index(self) -> int:
        return self._z_index

    @z_index.setter
    def z_index(self, value: int) -> None:
        normalized = int(value)
        if normalized == self._z_index:
            return
        self._z_index = normalized
        self.invalidate(reason="z_index")

    @property
    def clip_to_bounds(self) -> bool:
        return self._clip_to_bounds

    @clip_to_bounds.setter
    def clip_to_bounds(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._clip_to_bounds:
            return
        self._clip_to_bounds = normalized
        self.invalidate(reason="clip_to_bounds")

    @property
    def layout_constraints(self) -> LayoutConstraints:
        return self._layout_constraints

    @layout_constraints.setter
    def layout_constraints(self, value: LayoutConstraints) -> None:
        if value == self._layout_constraints:
            return
        self._layout_constraints = value
        self.invalidate(reason="layout_constraints")

    @property
    def layout_grow(self) -> float:
        return self._layout_grow

    @layout_grow.setter
    def layout_grow(self, value: float) -> None:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError("layout_grow must be a finite non-negative value.")
        if normalized == self._layout_grow:
            return
        self._layout_grow = normalized
        self.invalidate(reason="layout_grow")

    def set_layout_constraints(
        self,
        *,
        min_width: float = 0.0,
        min_height: float = 0.0,
        max_width: float = math.inf,
        max_height: float = math.inf,
    ) -> Widget:
        self.layout_constraints = LayoutConstraints(
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
        )
        return self

    def set_layout_grow(self, grow: float) -> Widget:
        self.layout_grow = grow
        return self

    def measure(self, available: Size | None = None) -> Size:
        """Return this widget's preferred constrained logical-DIP size."""

        preferred = self.layout_constraints.constrain(self.bounds.size)
        if available is None:
            return preferred
        available_width = max(0.0, float(available.width))
        available_height = max(0.0, float(available.height))
        return self.layout_constraints.constrain(
            Size(
                min(preferred.width, available_width),
                min(preferred.height, available_height),
            )
        )

    def build_scene_node(self) -> SceneNode:
        """Compile this widget's own visual node.

        Component children are attached later by the widget runtime so visual
        compilation preserves the logical component hierarchy automatically.
        """

        raise NotImplementedError

    def _set_layout_bounds(self, value: Rect) -> None:
        """Apply bounds inside an active layout pass without recursive invalidation."""

        self._bounds = value

    @staticmethod
    def _validate_opacity(value: float) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError("opacity must be finite and between 0.0 and 1.0.")
        return normalized
