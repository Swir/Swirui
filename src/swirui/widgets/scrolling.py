"""Retained clipped scrolling viewport for the SwirUI core-widget layer."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_PAGE_UP = 0x21
_VK_PAGE_DOWN = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_TRANSPARENT = Color(0.0, 0.0, 0.0, 0.0)


class ScrollView(Widget):
    """Focusable retained viewport with clipped, translated child content.

    Direct children use content-local logical-DIP coordinates. During scene
    compilation those retained child nodes are translated into the viewport and
    clipped by the existing SceneGraph compositing path. The component geometry
    itself remains unchanged, so scrolling never mutates public widget bounds.

    ``content_width`` and ``content_height`` are optional minimum extents. When
    omitted, the viewport measures the compiled child subtree and grows its
    scrollable extent automatically.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        content_width: float | None = None,
        content_height: float | None = None,
        scroll_x: float = 0.0,
        scroll_y: float = 0.0,
        line_step: float = 40.0,
        page_overlap: float = 24.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._declared_content_width = self._validate_optional_extent(
            content_width, "content_width"
        )
        self._declared_content_height = self._validate_optional_extent(
            content_height, "content_height"
        )
        self._measured_content_width = bounds.width
        self._measured_content_height = bounds.height
        self._scroll_x = self._validate_finite(scroll_x, "scroll_x")
        self._scroll_y = self._validate_finite(scroll_y, "scroll_y")
        self._line_step = self._validate_positive(line_step, "line_step")
        self._page_overlap = self._validate_non_negative(page_overlap, "page_overlap")
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name or "Scrollable content",
            accessible_description=accessible_description,
        )
        self._scroll_x = self._clamp_x(self._scroll_x)
        self._scroll_y = self._clamp_y(self._scroll_y)
        self._sync_accessibility()
        self.on("key_down", self._on_key_down)
        self.on("invalidated", self._on_invalidated)

    @property
    def scroll_x(self) -> float:
        return self._scroll_x

    @scroll_x.setter
    def scroll_x(self, value: float) -> None:
        self.scroll_to(x=value)

    @property
    def scroll_y(self) -> float:
        return self._scroll_y

    @scroll_y.setter
    def scroll_y(self, value: float) -> None:
        self.scroll_to(y=value)

    @property
    def content_width(self) -> float:
        return max(
            self.bounds.width,
            self._measured_content_width,
            self._declared_content_width or 0.0,
        )

    @property
    def content_height(self) -> float:
        return max(
            self.bounds.height,
            self._measured_content_height,
            self._declared_content_height or 0.0,
        )

    @property
    def max_scroll_x(self) -> float:
        return max(0.0, self.content_width - self.bounds.width)

    @property
    def max_scroll_y(self) -> float:
        return max(0.0, self.content_height - self.bounds.height)

    @property
    def line_step(self) -> float:
        return self._line_step

    @line_step.setter
    def line_step(self, value: float) -> None:
        normalized = self._validate_positive(value, "line_step")
        if normalized == self._line_step:
            return
        self._line_step = normalized
        self.invalidate(reason="line_step")

    def set_content_size(
        self,
        *,
        width: float | None = None,
        height: float | None = None,
    ) -> None:
        """Set minimum content extents, using ``None`` to return an axis to auto-size."""

        normalized_width = self._validate_optional_extent(width, "content_width")
        normalized_height = self._validate_optional_extent(height, "content_height")
        if (
            normalized_width == self._declared_content_width
            and normalized_height == self._declared_content_height
        ):
            return

        self._declared_content_width = normalized_width
        self._declared_content_height = normalized_height
        old_offset = (self._scroll_x, self._scroll_y)
        self._scroll_x = self._clamp_x(self._scroll_x)
        self._scroll_y = self._clamp_y(self._scroll_y)
        self._sync_accessibility()
        self.invalidate(reason="content_size")
        if old_offset != (self._scroll_x, self._scroll_y):
            self.emit(
                "scrolled",
                old_offset=old_offset,
                offset=(self._scroll_x, self._scroll_y),
                max_offset=(self.max_scroll_x, self.max_scroll_y),
            )

    def scroll_to(self, *, x: float | None = None, y: float | None = None) -> bool:
        """Clamp and apply a logical-DIP scroll offset.

        Returns ``True`` only when the effective offset changed.
        """

        requested_x = self._scroll_x if x is None else self._validate_finite(x, "scroll_x")
        requested_y = self._scroll_y if y is None else self._validate_finite(y, "scroll_y")
        new_x = self._clamp_x(requested_x)
        new_y = self._clamp_y(requested_y)
        old_offset = (self._scroll_x, self._scroll_y)
        new_offset = (new_x, new_y)
        if new_offset == old_offset:
            return False

        self._scroll_x, self._scroll_y = new_offset
        self._sync_accessibility()
        self.invalidate(reason="scroll_offset")
        self.emit(
            "scrolled",
            old_offset=old_offset,
            offset=new_offset,
            max_offset=(self.max_scroll_x, self.max_scroll_y),
        )
        return True

    def scroll_by(self, *, dx: float = 0.0, dy: float = 0.0) -> bool:
        """Move by a finite logical-DIP delta and clamp to the content extent."""

        delta_x = self._validate_finite(dx, "dx")
        delta_y = self._validate_finite(dy, "dy")
        return self.scroll_to(x=self._scroll_x + delta_x, y=self._scroll_y + delta_y)

    def build_scene_node(self) -> SceneNode:
        # A transparent group fill gives the empty viewport a stable hit target
        # without adding visible pixels. Descendants remain the topmost targets.
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_TRANSPARENT,
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )

    def prepare_scene_children(
        self,
        children: tuple[SceneNode, ...],
    ) -> tuple[SceneNode, ...]:
        """Measure content, clamp offsets, and translate children into the viewport."""

        measured_width = self.bounds.width
        measured_height = self.bounds.height
        for child in children:
            for node in child.walk():
                measured_width = max(measured_width, node.bounds.right)
                measured_height = max(measured_height, node.bounds.bottom)

        self._measured_content_width = measured_width
        self._measured_content_height = measured_height

        # Content may shrink between retained rebuilds. Clamp internally without
        # recursively invalidating during scene compilation.
        self._scroll_x = self._clamp_x(self._scroll_x)
        self._scroll_y = self._clamp_y(self._scroll_y)
        self._sync_accessibility()

        dx = self.bounds.x - self._scroll_x
        dy = self.bounds.y - self._scroll_y
        for child in children:
            self._translate_subtree(child, dx=dx, dy=dy)
        return children

    def _on_key_down(self, event: Event) -> None:
        if event.default_prevented or not self.enabled:
            return
        platform_event = event.data.get("event")
        if (
            not isinstance(platform_event, PlatformEvent)
            or platform_event.kind is not PlatformEventKind.KEY_DOWN
        ):
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        key_code = platform_event.key_code
        page_y = max(self.line_step, self.bounds.height - self._page_overlap)
        changed = False
        if key_code == _VK_LEFT:
            changed = self.scroll_by(dx=-self.line_step)
        elif key_code == _VK_RIGHT:
            changed = self.scroll_by(dx=self.line_step)
        elif key_code == _VK_UP:
            changed = self.scroll_by(dy=-self.line_step)
        elif key_code == _VK_DOWN:
            changed = self.scroll_by(dy=self.line_step)
        elif key_code == _VK_PAGE_UP:
            changed = self.scroll_by(dy=-page_y)
        elif key_code == _VK_PAGE_DOWN:
            changed = self.scroll_by(dy=page_y)
        elif key_code == _VK_HOME:
            changed = self.scroll_to(x=0.0, y=0.0)
        elif key_code == _VK_END:
            changed = self.scroll_to(x=self.max_scroll_x, y=self.max_scroll_y)

        if changed:
            event.prevent_default()

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") != "bounds":
            return
        self._scroll_x = self._clamp_x(self._scroll_x)
        self._scroll_y = self._clamp_y(self._scroll_y)
        self._sync_accessibility()

    def _sync_accessibility(self) -> None:
        self.accessible_value = self._scroll_y
        self.accessible_min_value = 0.0
        self.accessible_max_value = self.max_scroll_y
        self.accessible_value_text = (
            f"vertical {self._scroll_y:.0f} of {self.max_scroll_y:.0f} DIPs; "
            f"horizontal {self._scroll_x:.0f} of {self.max_scroll_x:.0f} DIPs"
        )

    def _clamp_x(self, value: float) -> float:
        return min(max(0.0, value), self.max_scroll_x)

    def _clamp_y(self, value: float) -> float:
        return min(max(0.0, value), self.max_scroll_y)

    @classmethod
    def _translate_subtree(cls, node: SceneNode, *, dx: float, dy: float) -> None:
        bounds = node.bounds
        node.bounds = Rect(bounds.x + dx, bounds.y + dy, bounds.width, bounds.height)
        for child in node.children:
            cls._translate_subtree(child, dx=dx, dy=dy)

    @staticmethod
    def _validate_finite(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite.")
        return normalized

    @classmethod
    def _validate_positive(cls, value: float, name: str) -> float:
        normalized = cls._validate_finite(value, name)
        if normalized <= 0.0:
            raise ValueError(f"{name} must be greater than zero.")
        return normalized

    @classmethod
    def _validate_non_negative(cls, value: float, name: str) -> float:
        normalized = cls._validate_finite(value, name)
        if normalized < 0.0:
            raise ValueError(f"{name} must be non-negative.")
        return normalized

    @classmethod
    def _validate_optional_extent(cls, value: float | None, name: str) -> float | None:
        if value is None:
            return None
        return cls._validate_non_negative(value, name)
