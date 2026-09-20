"""Retained professional tab container for SwirUI."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from swirui.core import (
    AccessibilityNode,
    AccessibilityRole,
    Component,
    Event,
    build_accessibility_tree,
)
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_HOME = 0x24
_VK_END = 0x23
_VK_LEFT = 0x25
_VK_RIGHT = 0x27

_DEFAULT_BACKGROUND = Color.from_hex("#07111C")
_DEFAULT_TAB_BACKGROUND = Color.from_hex("#081723")
_DEFAULT_ACTIVE_TAB_BACKGROUND = Color.from_hex("#0B3550")
_DEFAULT_FOREGROUND = Color.from_hex("#DDF5FF")
_DEFAULT_MUTED = Color.from_hex("#8DA8B8")
_DEFAULT_ACCENT = Color.from_hex("#23C9FF")


@dataclass(frozen=True, slots=True)
class TabItem:
    """Immutable tab descriptor with stable application identity and retained content."""

    key: Hashable
    label: str
    content: Component
    disabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("TabItem.key must be hashable.")
        if not self.label.strip():
            raise ValueError("TabItem.label must not be empty.")
        if not isinstance(self.content, Component):
            raise TypeError("TabItem.content must be a Component.")


class Tabs(Widget):
    """Focusable retained tabs with stable-key selection and managed page visibility.

    Only the selected page participates in rendering, hit testing and accessibility.
    Widget page content is arranged into the content region below the tab strip while
    preserving its authored preferred size for later reuse outside the container.
    """

    def __init__(
        self,
        tabs: Sequence[TabItem],
        *,
        bounds: Rect,
        key: str | None = None,
        selected_key: Hashable | None = None,
        header_height: float = 42.0,
        corner_radius: float = 8.0,
        font_size: float = 14.0,
        font_family: str = "Segoe UI",
        background: Color | None = None,
        tab_background: Color | None = None,
        active_tab_background: Color | None = None,
        foreground: Color | None = None,
        muted_foreground: Color | None = None,
        accent: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Tabs",
        accessible_description: str | None = None,
    ) -> None:
        self._tabs = self._validate_tabs(tabs)
        self._header_height = self._validate_positive(header_height, "header_height")
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = str(font_family).strip()
        if not self._font_family:
            raise ValueError("font_family must not be empty.")
        self._background = background or _DEFAULT_BACKGROUND
        self._tab_background = tab_background or _DEFAULT_TAB_BACKGROUND
        self._active_tab_background = active_tab_background or _DEFAULT_ACTIVE_TAB_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._muted_foreground = muted_foreground or _DEFAULT_MUTED
        self._accent = accent or _DEFAULT_ACCENT
        self._selected_index = self._initial_selection(selected_key)

        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self._attach_contents()
        self._sync_accessibility_value()

    @property
    def tabs(self) -> tuple[TabItem, ...]:
        return self._tabs

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_tab(self) -> TabItem | None:
        if self._selected_index is None:
            return None
        return self._tabs[self._selected_index]

    @property
    def selected_key(self) -> Hashable | None:
        selected = self.selected_tab
        return None if selected is None else selected.key

    @property
    def header_height(self) -> float:
        return min(self._header_height, self.bounds.height)

    @property
    def content_bounds(self) -> Rect:
        header = self.header_height
        return Rect(
            self.bounds.x,
            self.bounds.y + header,
            self.bounds.width,
            max(0.0, self.bounds.height - header),
        )

    def set_tabs(self, tabs: Sequence[TabItem]) -> Tabs:
        """Replace tabs while preserving selection by stable key when possible."""

        normalized = self._validate_tabs(tabs)
        if normalized == self._tabs:
            return self
        selected_key = self.selected_key
        for child in tuple(self.children):
            super().remove(child)
        self._tabs = normalized
        self._selected_index = self._index_for_key(selected_key)
        if self._selected_index is None or self._tabs[self._selected_index].disabled:
            self._selected_index = self._first_enabled_index()
        self._attach_contents()
        self._sync_accessibility_value()
        self.invalidate(reason="tabs")
        return self

    def select_index(self, index: int) -> Tabs:
        normalized = self._normalize_index(index)
        if self._tabs[normalized].disabled or normalized == self._selected_index:
            return self
        previous = self.selected_tab
        self._selected_index = normalized
        self._sync_content_visibility()
        self._sync_accessibility_value()
        selected = self._tabs[normalized]
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=normalized,
            key=selected.key,
            tab=selected,
            previous=previous,
        )
        return self

    def select_key(self, key: Hashable) -> Tabs:
        index = self._index_for_key(key)
        if index is None:
            raise KeyError(f"Unknown tab key: {key!r}")
        return self.select_index(index)

    def prepare_layout(self, viewport: Rect) -> None:
        """Arrange the selected widget page into the content region."""

        _ = viewport
        selected = self.selected_tab
        if selected is not None and isinstance(selected.content, Widget):
            selected.content._set_layout_bounds(self.content_bounds)

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
            hit_testable=self.enabled,
        )
        if not self._tabs or self.bounds.width <= 0.0 or self.header_height <= 0.0:
            return root

        tab_width = self.bounds.width / len(self._tabs)
        for index, tab in enumerate(self._tabs):
            x = self.bounds.x + tab_width * index
            width = self.bounds.right - x if index == len(self._tabs) - 1 else tab_width
            tab_bounds = Rect(x, self.bounds.y, max(0.0, width), self.header_height)
            active = index == self._selected_index
            tab_node = SceneNode(
                key=f"{self.key}:tab:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=tab_bounds,
                fill=self._active_tab_background if active else self._tab_background,
                z_index=1,
                hit_testable=False,
            )
            text_height = min(tab_bounds.height, self._font_size * 1.35)
            tab_node.add(
                SceneNode(
                    key=f"{self.key}:tab:{index}:label",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        tab_bounds.x + 10.0,
                        tab_bounds.y + max(0.0, (tab_bounds.height - text_height) * 0.5),
                        max(0.0, tab_bounds.width - 20.0),
                        text_height,
                    ),
                    fill=(
                        self._muted_foreground
                        if tab.disabled
                        else self._foreground
                    ),
                    text=tab.label,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    z_index=2,
                    hit_testable=False,
                )
            )
            if active:
                tab_node.add(
                    SceneNode(
                        key=f"{self.key}:tab:{index}:accent",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            tab_bounds.x,
                            tab_bounds.bottom - 2.0,
                            tab_bounds.width,
                            2.0,
                        ),
                        fill=self._accent,
                        z_index=3,
                        hit_testable=False,
                    )
                )
            root.add(tab_node)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children: list[AccessibilityNode] = []
        for index, tab in enumerate(self._tabs):
            active = index == self._selected_index
            children.append(
                AccessibilityNode(
                    key=f"{self.key}:a11y:tab:{index}",
                    role=AccessibilityRole.BUTTON,
                    name=tab.label,
                    description=None,
                    enabled=self.enabled and not tab.disabled,
                    focusable=False,
                    focused=False,
                    selected=active,
                    active=active,
                )
            )
        selected = self.selected_tab
        if selected is not None:
            content = build_accessibility_tree(selected.content, focused=focused)
            if content is not None:
                children.append(content)
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=tuple(children),
        )

    def _attach_contents(self) -> None:
        if self._tabs:
            super().add(*(tab.content for tab in self._tabs))
        self._sync_content_visibility()

    def _sync_content_visibility(self) -> None:
        for index, tab in enumerate(self._tabs):
            tab.content.visible = index == self._selected_index

    def _sync_accessibility_value(self) -> None:
        selected = self.selected_tab
        if selected is None:
            self.accessible_value_text = f"No tab selected of {len(self._tabs)}"
        else:
            self.accessible_value_text = (
                f"{selected.label} selected, {self._selected_index + 1} of {len(self._tabs)}"
            )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
            or not self._point_in_header(platform_event.x, platform_event.y)
            or not self._tabs
        ):
            return
        relative_x = platform_event.x - self.bounds.x
        tab_width = self.bounds.width / len(self._tabs)
        index = min(len(self._tabs) - 1, max(0, int(relative_x // tab_width)))
        self.select_index(index)
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._tabs:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        target = self._navigation_target(platform_event.key_code)
        if target is None:
            return
        self.select_index(target)
        event.prevent_default()

    def _navigation_target(self, key_code: int | None) -> int | None:
        if key_code == _VK_HOME:
            return self._first_enabled_index()
        if key_code == _VK_END:
            return self._last_enabled_index()
        if key_code not in {_VK_LEFT, _VK_RIGHT}:
            return None
        if self._selected_index is None:
            return self._first_enabled_index()
        step = -1 if key_code == _VK_LEFT else 1
        index = self._selected_index
        for _ in range(len(self._tabs)):
            index = (index + step) % len(self._tabs)
            if not self._tabs[index].disabled:
                return index
        return self._selected_index

    def _initial_selection(self, selected_key: Hashable | None) -> int | None:
        if selected_key is None:
            return self._first_enabled_index()
        index = self._index_for_key(selected_key)
        if index is None:
            raise KeyError(f"Unknown selected tab key: {selected_key!r}")
        if self._tabs[index].disabled:
            raise ValueError("selected_key cannot refer to a disabled tab.")
        return index

    def _first_enabled_index(self) -> int | None:
        return next((index for index, tab in enumerate(self._tabs) if not tab.disabled), None)

    def _last_enabled_index(self) -> int | None:
        return next(
            (
                index
                for index in range(len(self._tabs) - 1, -1, -1)
                if not self._tabs[index].disabled
            ),
            None,
        )

    def _index_for_key(self, key: Hashable | None) -> int | None:
        if key is None:
            return None
        return next((index for index, tab in enumerate(self._tabs) if tab.key == key), None)

    def _normalize_index(self, index: int) -> int:
        normalized = int(index)
        if not 0 <= normalized < len(self._tabs):
            raise IndexError("Tabs index is out of range.")
        return normalized

    def _point_in_header(self, x: float, y: float) -> bool:
        return (
            self.bounds.x <= x < self.bounds.right
            and self.bounds.y <= y < self.bounds.y + self.header_height
        )

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_tabs(tabs: Sequence[TabItem]) -> tuple[TabItem, ...]:
        normalized = tuple(tabs)
        seen_keys: set[Hashable] = set()
        seen_content: set[int] = set()
        for tab in normalized:
            if tab.key in seen_keys:
                raise ValueError(f"Tabs keys must be unique; duplicate {tab.key!r}.")
            content_id = id(tab.content)
            if content_id in seen_content:
                raise ValueError("Each tab must own a distinct content component.")
            seen_keys.add(tab.key)
            seen_content.add(content_id)
        return normalized

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and positive.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized
