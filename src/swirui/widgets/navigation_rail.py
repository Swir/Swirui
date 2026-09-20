"""Retained sidebar and navigation-rail widgets for professional SwirUI apps."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_HOME = 0x24
_VK_END = 0x23
_VK_UP = 0x26
_VK_DOWN = 0x28

_DEFAULT_BACKGROUND = Color.from_hex("#06101A")
_DEFAULT_ITEM_BACKGROUND = Color.from_hex("#081723")
_DEFAULT_ACTIVE_ITEM_BACKGROUND = Color.from_hex("#0B3550")
_DEFAULT_FOREGROUND = Color.from_hex("#DDF5FF")
_DEFAULT_MUTED = Color.from_hex("#8DA8B8")
_DEFAULT_ACCENT = Color.from_hex("#23C9FF")


@dataclass(frozen=True, slots=True)
class NavigationItem:
    """Immutable navigation descriptor with stable application identity."""

    key: Hashable
    label: str
    short_label: str | None = None
    disabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("NavigationItem.key must be hashable.")
        label = self.label.strip()
        if not label:
            raise ValueError("NavigationItem.label must not be empty.")
        object.__setattr__(self, "label", label)
        if self.short_label is not None:
            short_label = self.short_label.strip()
            if not short_label:
                raise ValueError("NavigationItem.short_label must not be empty when provided.")
            object.__setattr__(self, "short_label", short_label)


class NavigationRail(Widget):
    """Focusable retained vertical navigation with stable-key selection.

    The rail owns selection only; applications can react to ``selection_changed`` and
    compose page content independently. ``expanded`` switches between compact labels
    and full sidebar-style labels without replacing the retained component.
    """

    def __init__(
        self,
        items: Sequence[NavigationItem],
        *,
        bounds: Rect,
        key: str | None = None,
        selected_key: Hashable | None = None,
        expanded: bool = False,
        item_height: float = 48.0,
        corner_radius: float = 8.0,
        font_size: float = 14.0,
        font_family: str = "Segoe UI",
        background: Color | None = None,
        item_background: Color | None = None,
        active_item_background: Color | None = None,
        foreground: Color | None = None,
        muted_foreground: Color | None = None,
        accent: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Navigation rail",
        accessible_description: str | None = None,
    ) -> None:
        self._items = self._validate_items(items)
        self._expanded = bool(expanded)
        self._item_height = self._validate_positive(item_height, "item_height")
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = str(font_family).strip()
        if not self._font_family:
            raise ValueError("font_family must not be empty.")
        self._background = background or _DEFAULT_BACKGROUND
        self._item_background = item_background or _DEFAULT_ITEM_BACKGROUND
        self._active_item_background = active_item_background or _DEFAULT_ACTIVE_ITEM_BACKGROUND
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
            accessibility_role=AccessibilityRole.LIST,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self._sync_accessibility_value()

    @property
    def items(self) -> tuple[NavigationItem, ...]:
        return self._items

    @property
    def expanded(self) -> bool:
        return self._expanded

    @property
    def item_height(self) -> float:
        return self._item_height

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_item(self) -> NavigationItem | None:
        if self._selected_index is None:
            return None
        return self._items[self._selected_index]

    @property
    def selected_key(self) -> Hashable | None:
        selected = self.selected_item
        return None if selected is None else selected.key

    def set_items(self, items: Sequence[NavigationItem]) -> NavigationRail:
        """Replace descriptors while preserving selection by stable key when possible."""

        normalized = self._validate_items(items)
        if normalized == self._items:
            return self
        selected_key = self.selected_key
        self._items = normalized
        self._selected_index = self._index_for_key(selected_key)
        if self._selected_index is None or self._items[self._selected_index].disabled:
            self._selected_index = self._first_enabled_index()
        self._sync_accessibility_value()
        self.invalidate(reason="items")
        return self

    def set_expanded(self, expanded: bool) -> NavigationRail:
        """Switch compact rail / expanded sidebar presentation in-place."""

        normalized = bool(expanded)
        if normalized == self._expanded:
            return self
        self._expanded = normalized
        self.invalidate(reason="expanded")
        self.emit("expanded_changed", expanded=normalized)
        return self

    def select_index(self, index: int) -> NavigationRail:
        normalized = self._normalize_index(index)
        if self._items[normalized].disabled or normalized == self._selected_index:
            return self
        previous = self.selected_item
        self._selected_index = normalized
        selected = self._items[normalized]
        self._sync_accessibility_value()
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=normalized,
            key=selected.key,
            item=selected,
            previous=previous,
        )
        return self

    def select_key(self, key: Hashable) -> NavigationRail:
        index = self._index_for_key(key)
        if index is None:
            raise KeyError(f"Unknown navigation key: {key!r}")
        return self.select_index(index)

    def item_bounds(self, index: int) -> Rect:
        """Return the logical-DIP bounds for one navigation row."""

        normalized = self._normalize_index(index)
        return Rect(
            self.bounds.x,
            self.bounds.y + self._item_height * normalized,
            self.bounds.width,
            self._item_height,
        )

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
        if self.bounds.width <= 0.0 or self.bounds.height <= 0.0:
            return root

        for index, item in enumerate(self._items):
            row = self.item_bounds(index)
            if row.y >= self.bounds.bottom:
                break
            active = index == self._selected_index
            row_node = SceneNode(
                key=f"{self.key}:item:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row,
                fill=self._active_item_background if active else self._item_background,
                z_index=1,
                hit_testable=False,
            )
            if active:
                row_node.add(
                    SceneNode(
                        key=f"{self.key}:item:{index}:accent",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(row.x, row.y + 6.0, 3.0, max(0.0, row.height - 12.0)),
                        fill=self._accent,
                        z_index=2,
                        hit_testable=False,
                    )
                )
            label = item.label if self._expanded else (item.short_label or item.label)
            text_height = min(row.height, self._font_size * 1.35)
            row_node.add(
                SceneNode(
                    key=f"{self.key}:item:{index}:label",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        row.x + (16.0 if self._expanded else 10.0),
                        row.y + max(0.0, (row.height - text_height) * 0.5),
                        max(0.0, row.width - (28.0 if self._expanded else 20.0)),
                        text_height,
                    ),
                    fill=self._muted_foreground if item.disabled else self._foreground,
                    text=label,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    z_index=3,
                    hit_testable=False,
                )
            )
            root.add(row_node)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:item:{index}",
                role=AccessibilityRole.LIST_ITEM,
                name=item.label,
                description=None,
                enabled=self.enabled and not item.disabled,
                focusable=False,
                focused=False,
                selected=index == self._selected_index,
                active=index == self._selected_index,
                row_index=index,
                row_count=len(self._items),
            )
            for index, item in enumerate(self._items)
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.LIST,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            row_count=len(self._items),
            children=children,
        )

    def _sync_accessibility_value(self) -> None:
        selected = self.selected_item
        index = self._selected_index
        if selected is None or index is None:
            self.accessible_value_text = f"No item selected of {len(self._items)}"
        else:
            self.accessible_value_text = (
                f"{selected.label} selected, {index + 1} of {len(self._items)}"
            )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
            or not (
                self.bounds.x <= platform_event.x < self.bounds.right
                and self.bounds.y <= platform_event.y < self.bounds.bottom
            )
            or not self._items
        ):
            return
        index = int((platform_event.y - self.bounds.y) // self._item_height)
        if 0 <= index < len(self._items):
            self.select_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._items:
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
        if key_code not in {_VK_UP, _VK_DOWN}:
            return None
        if self._selected_index is None:
            return self._first_enabled_index()
        step = -1 if key_code == _VK_UP else 1
        index = self._selected_index
        for _ in range(len(self._items)):
            index = (index + step) % len(self._items)
            if not self._items[index].disabled:
                return index
        return self._selected_index

    def _initial_selection(self, selected_key: Hashable | None) -> int | None:
        if selected_key is None:
            return self._first_enabled_index()
        index = self._index_for_key(selected_key)
        if index is None:
            raise KeyError(f"Unknown selected navigation key: {selected_key!r}")
        if self._items[index].disabled:
            raise ValueError("selected_key cannot refer to a disabled navigation item.")
        return index

    def _first_enabled_index(self) -> int | None:
        return next((index for index, item in enumerate(self._items) if not item.disabled), None)

    def _last_enabled_index(self) -> int | None:
        return next(
            (
                index
                for index in range(len(self._items) - 1, -1, -1)
                if not self._items[index].disabled
            ),
            None,
        )

    def _index_for_key(self, key: Hashable | None) -> int | None:
        if key is None:
            return None
        return next((index for index, item in enumerate(self._items) if item.key == key), None)

    def _normalize_index(self, index: int) -> int:
        normalized = int(index)
        if not 0 <= normalized < len(self._items):
            raise IndexError("NavigationRail index is out of range.")
        return normalized

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_items(items: Sequence[NavigationItem]) -> tuple[NavigationItem, ...]:
        normalized = tuple(items)
        keys: set[Hashable] = set()
        for item in normalized:
            if not isinstance(item, NavigationItem):
                raise TypeError("NavigationRail items must be NavigationItem values.")
            if item.key in keys:
                raise ValueError(f"Duplicate navigation key: {item.key!r}")
            keys.add(item.key)
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


class Sidebar(NavigationRail):
    """Expanded NavigationRail convenience widget for application sidebars."""

    def __init__(
        self,
        items: Sequence[NavigationItem],
        *,
        bounds: Rect,
        key: str | None = None,
        selected_key: Hashable | None = None,
        item_height: float = 44.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Sidebar",
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            items,
            bounds=bounds,
            key=key,
            selected_key=selected_key,
            expanded=True,
            item_height=item_height,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
