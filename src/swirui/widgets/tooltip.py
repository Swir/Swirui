"""Retained tooltip widget bound to pointer/focus state of a target component."""

from __future__ import annotations

import math
from collections.abc import Callable

from swirui.core import AccessibilityRole, Component, Event
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_BACKGROUND = Color.from_hex("#0B1B26")
_FOREGROUND = Color.from_hex("#EAF8FF")


class Tooltip(Widget):
    """Non-interactive retained tooltip shown for target hover or keyboard focus."""

    def __init__(
        self,
        text: str,
        *,
        target: Component,
        bounds: Rect,
        key: str | None = None,
        background: Color | None = None,
        foreground: Color | None = None,
        corner_radius: float = 7.0,
        font_size: float = 13.0,
        font_family: str = "Segoe UI",
        padding: float = 9.0,
        show_on_focus: bool = True,
        opacity: float = 1.0,
        z_index: int = 10_000,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._text = str(text)
        self._target = target
        self._background = background or _BACKGROUND
        self._foreground = foreground or _FOREGROUND
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._show_on_focus = bool(show_on_focus)
        self._target_hovered = False
        self._target_focused = False
        self._auto_accessible_name = accessible_name is None
        self._subscriptions: list[Callable[[], None]] = []
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=False,
            accessibility_role=AccessibilityRole.TOOLTIP,
            accessible_name=self._text if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )
        self._visible = False
        self._subscriptions = [
            target.on("pointer_enter", self._on_pointer_enter),
            target.on("pointer_leave", self._on_pointer_leave),
            target.on("focus_gained", self._on_focus_gained),
            target.on("focus_lost", self._on_focus_lost),
            target.on("invalidated", self._on_target_invalidated),
        ]

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
    def target(self) -> Component:
        return self._target

    @property
    def show_on_focus(self) -> bool:
        return self._show_on_focus

    @show_on_focus.setter
    def show_on_focus(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._show_on_focus:
            return
        self._show_on_focus = normalized
        self._sync_visibility()

    def show(self) -> None:
        if not self.visible:
            self.visible = True

    def hide(self) -> None:
        if self.visible:
            self.visible = False

    def detach(self) -> None:
        """Detach target listeners while leaving the tooltip component reusable."""

        for unsubscribe in self._subscriptions:
            unsubscribe()
        self._subscriptions.clear()
        self._target_hovered = False
        self._target_focused = False
        self.hide()

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
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
        content_width = max(0.0, self.bounds.width - 2.0 * self._padding)
        if self.text and content_width > 0.0 and self.bounds.height > 0.0:
            line_height = min(self.bounds.height, self._font_size * 1.25)
            root.add(
                SceneNode(
                    key=f"{self.key}:content",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        self.bounds.x + self._padding,
                        self.bounds.y + max(0.0, (self.bounds.height - line_height) / 2.0),
                        content_width,
                        line_height,
                    ),
                    fill=self._foreground,
                    text=self.text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        return root

    def _on_pointer_enter(self, _event: Event) -> None:
        if self._target.enabled and self._target.visible:
            self._target_hovered = True
        self._sync_visibility()

    def _on_pointer_leave(self, _event: Event) -> None:
        self._target_hovered = False
        self._sync_visibility()

    def _on_focus_gained(self, _event: Event) -> None:
        if self._target.enabled and self._target.visible:
            self._target_focused = True
        self._sync_visibility()

    def _on_focus_lost(self, _event: Event) -> None:
        self._target_focused = False
        self._sync_visibility()

    def _on_target_invalidated(self, event: Event) -> None:
        if event.data.get("reason") not in {"enabled", "visible"}:
            return
        if not self._target.enabled or not self._target.visible:
            self._target_hovered = False
            self._target_focused = False
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        should_show = (
            self._target.enabled
            and self._target.visible
            and (self._target_hovered or (self._show_on_focus and self._target_focused))
        )
        if should_show != self.visible:
            self.visible = should_show

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
