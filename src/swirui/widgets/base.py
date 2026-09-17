"""Retained visual widget foundation for SwirUI."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole, Component
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNode


class Widget(Component):
    """Base component with retained visual geometry.

    Widgets author logical-DIP geometry and compile it to backend-neutral
    :class:`~swirui.rendering.scene.SceneNode` objects. The existing renderer
    pipeline remains responsible for HiDPI conversion and native GPU submission.
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

    def build_scene_node(self) -> SceneNode:
        """Compile this widget's own visual node.

        Component children are attached later by the widget runtime so visual
        compilation preserves the logical component hierarchy automatically.
        """

        raise NotImplementedError

    @staticmethod
    def _validate_opacity(value: float) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError("opacity must be finite and between 0.0 and 1.0.")
        return normalized
