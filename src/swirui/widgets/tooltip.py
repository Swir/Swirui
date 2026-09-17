"""Retained tooltip overlay control for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Callable

from swirui.core import AccessibilityRole, Component, Event
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_DEFAULT_BACKGROUND = Color.from_hex("#08131F")
_DEFAULT_FOREGROUND = Color.from_hex("#EAF8FF")


class Tooltip(Widget):
    """Non-interactive retained tooltip that can follow hover and keyboard focus."""

    def __init__(
        self,
        text: str,
        *,
        bounds: Rect,
        target: Component | None = None,
        key: str | None = None,
        background: Color | None = None,
        foreground: Color | None = None,
        corner_radius: float = 8.0,
        font_size: float = 13.0,
        font_family: str = "Segoe UI",
        padding: float = 10.0,
        show_on_hover: bool = True,
        show_on_focus: bool = True,
        initially_open: bool = False,
        opacity: float = 1.0,
        z_index: int = 10_000,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._background = background or _DEFAULT_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._show_on_hover = bool(show_on_hover)
        self._show_on_focus = bool(show_on_focus)
        self._hover_open = False
        self._focus_open = False
        self._target: Component | None = None
        self._target_unsubscribers: list[Callable[[], None]] = []
        self._auto_accessible_name = accessible_name is None
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            accessibility_role=AccessibilityRole.TOOLTIP,
            accessible_name=self._text if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )
        self.visible = bool(initially_open)
        if target is not None:
            self.attach(target)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._text:
            return
        self._text = normalized
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="text")

    @property
    def target(self) -> Component | None:
        return self._target

    @property
    def is_open(self) -> bool:
        return self.visible

    def attach(self, target: Component | None) -> Tooltip:
        """Bind visibility to ``target`` hover/focus events, replacing any prior binding."""

        if target is self._target:
            return self
        self.detach()
        self._target = target
        if target is None:
            return self
        if self._show_on_hover:
            self._target_unsubscribers.extend(
                (
                    target.on("pointer_enter", self._on_target_pointer_enter),
                    target.on("pointer_leave", self._on_target_pointer_leave),
                )
            )
        if self._show_on_focus:
            self._target_unsubscribers.extend(
                (
                    target.on("focus_gained", self._on_target_focus_gained),
                    target.on("focus_lost", self._on_target_focus_lost),
                )
            )
        self._target_unsubscribers.append(target.on("invalidated", self._on_target_invalidated))
        return self

    def detach(self) -> None:
        """Detach target listeners and close the tooltip."""

        for unsubscribe in self._target_unsubscribers:
            unsubscribe()
        self._target_unsubscribers.clear()
        self._target = None
        self._hover_open = False
        self._focus_open = False
        if self.visible:
            self.visible = False

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self._hover_open = False
        self._focus_open = False
        self.visible = False

    def build_scene_node(self) -> SceneNode:
        node = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=False,
        )
        content_bounds = self._content_bounds()
        if self.text and content_bounds.width > 0.0 and content_bounds.height > 0.0:
            node.add(
                SceneNode(
                    key=f"{self.key}:text",
                    kind=SceneNodeKind.TEXT,
                    bounds=content_bounds,
                    fill=self._foreground,
                    text=self.text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        return node

    def _content_bounds(self) -> Rect:
        width = max(0.0, self.bounds.width - (2.0 * self._padding))
        line_height = self._font_size * 1.25
        height = min(self.bounds.height, line_height)
        y = self.bounds.y + max(0.0, (self.bounds.height - height) * 0.5)
        return Rect(self.bounds.x + self._padding, y, width, height)

    def _target_available(self) -> bool:
        component = self._target
        while component is not None:
            if not component.enabled or not component.visible:
                return False
            component = component.parent
        return True

    def _sync_target_visibility(self) -> None:
        self.visible = self._target_available() and (self._hover_open or self._focus_open)

    def _on_target_pointer_enter(self, _event: Event) -> None:
        self._hover_open = self._target_available()
        self._sync_target_visibility()

    def _on_target_pointer_leave(self, _event: Event) -> None:
        self._hover_open = False
        self._sync_target_visibility()

    def _on_target_focus_gained(self, _event: Event) -> None:
        self._focus_open = self._target_available()
        self._sync_target_visibility()

    def _on_target_focus_lost(self, _event: Event) -> None:
        self._focus_open = False
        self._sync_target_visibility()

    def _on_target_invalidated(self, event: Event) -> None:
        if event.data.get("reason") not in {"enabled", "visible"}:
            return
        if not self._target_available():
            self._hover_open = False
            self._focus_open = False
        self._sync_target_visibility()

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and greater than zero.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized

    @staticmethod
    def _validate_font_family(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("font_family cannot be empty.")
        return normalized
