"""Retained Timeline widget for professional SwirUI applications."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_BACKGROUND = Color.from_hex("#06101A")
_ITEM_BACKGROUND = Color.from_hex("#081723")
_SELECTED_BACKGROUND = Color.from_hex("#0B3550")
_FOREGROUND = Color.from_hex("#DDF5FF")
_MUTED = Color.from_hex("#8DA8B8")
_AXIS = Color.from_hex("#164D6B")
_ACCENT = Color.from_hex("#23C9FF")
_DISABLED = Color.from_hex("#456273")


class TimelineOrientation(StrEnum):
    """Layout direction used by retained Timeline."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


@dataclass(frozen=True, slots=True)
class TimelineItem:
    """Immutable timeline entry with stable identity and display metadata."""

    key: Hashable
    title: str
    timestamp: str
    description: str | None = None
    disabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("TimelineItem.key must be hashable.")
        title = self.title.strip()
        timestamp = self.timestamp.strip()
        if not title:
            raise ValueError("TimelineItem.title must not be empty.")
        if not timestamp:
            raise ValueError("TimelineItem.timestamp must not be empty.")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "timestamp", timestamp)
        if self.description is not None:
            description = self.description.strip()
            if not description:
                raise ValueError("TimelineItem.description must not be empty when provided.")
            object.__setattr__(self, "description", description)


class Timeline(Widget):
    """Focusable retained timeline with stable-key selection and activation."""

    def __init__(
        self,
        items: Sequence[TimelineItem],
        *,
        bounds: Rect,
        key: str | None = None,
        selected_key: Hashable | None = None,
        orientation: TimelineOrientation = TimelineOrientation.VERTICAL,
        item_extent: float = 78.0,
        marker_size: float = 12.0,
        line_thickness: float = 2.0,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Timeline",
        accessible_description: str | None = None,
    ) -> None:
        self._items = self._validate_items(items)
        if not isinstance(orientation, TimelineOrientation):
            raise TypeError("orientation must be TimelineOrientation.")
        self._orientation = orientation
        self._item_extent = self._positive(item_extent, "item_extent")
        self._marker_size = self._positive(marker_size, "marker_size")
        self._line_thickness = self._positive(line_thickness, "line_thickness")
        family = str(font_family).strip()
        if not family:
            raise ValueError("font_family must not be empty.")
        self._font_family = family
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
    def items(self) -> tuple[TimelineItem, ...]:
        return self._items

    @property
    def orientation(self) -> TimelineOrientation:
        return self._orientation

    @property
    def item_extent(self) -> float:
        return self._item_extent

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_item(self) -> TimelineItem | None:
        if self._selected_index is None:
            return None
        return self._items[self._selected_index]

    @property
    def selected_key(self) -> Hashable | None:
        item = self.selected_item
        return None if item is None else item.key

    def set_items(self, items: Sequence[TimelineItem]) -> Timeline:
        """Replace entries while preserving selection by stable key when possible."""

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
        self.emit("items_changed", count=len(self._items))
        return self

    def select_index(self, index: int) -> Timeline:
        normalized = self._normalize_index(index)
        item = self._items[normalized]
        if item.disabled or normalized == self._selected_index:
            return self
        previous = self.selected_item
        self._selected_index = normalized
        self._sync_accessibility_value()
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=normalized,
            key=item.key,
            item=item,
            previous=previous,
        )
        return self

    def select_key(self, key: Hashable) -> Timeline:
        index = self._index_for_key(key)
        if index is None:
            raise KeyError(f"Unknown timeline key: {key!r}")
        return self.select_index(index)

    def activate_selected(self) -> Timeline:
        item = self.selected_item
        index = self._selected_index
        if item is None or index is None or item.disabled:
            return self
        self.emit("item_activated", index=index, key=item.key, item=item)
        return self

    def item_bounds(self, index: int) -> Rect:
        normalized = self._normalize_index(index)
        if self._orientation is TimelineOrientation.VERTICAL:
            return Rect(
                self.bounds.x,
                self.bounds.y + self._item_extent * normalized,
                self.bounds.width,
                self._item_extent,
            )
        return Rect(
            self.bounds.x + self._item_extent * normalized,
            self.bounds.y,
            self._item_extent,
            self.bounds.height,
        )

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_BACKGROUND,
            corner_radius=CornerRadius.uniform(8.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        if not self._items or self.bounds.width <= 0.0 or self.bounds.height <= 0.0:
            return root

        root.add(self._build_axis())
        for index, item in enumerate(self._items):
            cell = self.item_bounds(index)
            if self._orientation is TimelineOrientation.VERTICAL:
                if cell.y >= self.bounds.bottom:
                    break
            elif cell.x >= self.bounds.right:
                break
            root.add(self._build_item(index, item, cell))
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
                name=item.title,
                description=self._semantic_description(item),
                enabled=self.enabled and not item.disabled,
                focusable=False,
                focused=False,
                selected=index == self._selected_index,
                active=index == self._selected_index,
                row_index=index,
                row_count=len(self._items),
                value_text=item.timestamp,
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

    def _build_axis(self) -> SceneNode:
        if self._orientation is TimelineOrientation.VERTICAL:
            x = self.bounds.x + 28.0 - self._line_thickness * 0.5
            return SceneNode(
                key=f"{self.key}:axis",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    x,
                    self.bounds.y + 18.0,
                    self._line_thickness,
                    max(0.0, self.bounds.height - 36.0),
                ),
                fill=_AXIS,
                z_index=1,
                hit_testable=False,
            )
        y = self.bounds.y + 30.0 - self._line_thickness * 0.5
        return SceneNode(
            key=f"{self.key}:axis",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(
                self.bounds.x + 18.0,
                y,
                max(0.0, self.bounds.width - 36.0),
                self._line_thickness,
            ),
            fill=_AXIS,
            z_index=1,
            hit_testable=False,
        )

    def _build_item(self, index: int, item: TimelineItem, cell: Rect) -> SceneNode:
        selected = index == self._selected_index
        node = SceneNode(
            key=f"{self.key}:item:{index}",
            kind=SceneNodeKind.RECTANGLE,
            bounds=cell,
            fill=_SELECTED_BACKGROUND if selected else _ITEM_BACKGROUND,
            corner_radius=CornerRadius.uniform(6.0),
            z_index=2,
            hit_testable=False,
        )
        if self._orientation is TimelineOrientation.VERTICAL:
            marker_x = cell.x + 28.0 - self._marker_size * 0.5
            marker_y = cell.y + self._item_extent * 0.5 - self._marker_size * 0.5
            text_x = cell.x + 52.0
            text_width = max(0.0, cell.right - text_x - 12.0)
            node.add(self._marker_node(index, item, marker_x, marker_y, selected))
            node.add(
                self._text_node(
                    f"{self.key}:item:{index}:time",
                    Rect(text_x, cell.y + 8.0, text_width, 16.0),
                    item.timestamp,
                    11.0,
                    _MUTED if not item.disabled else _DISABLED,
                    4,
                )
            )
            node.add(
                self._text_node(
                    f"{self.key}:item:{index}:title",
                    Rect(text_x, cell.y + 27.0, text_width, 20.0),
                    item.title,
                    14.0,
                    _FOREGROUND if not item.disabled else _DISABLED,
                    4,
                )
            )
            if item.description is not None:
                node.add(
                    self._text_node(
                        f"{self.key}:item:{index}:description",
                        Rect(text_x, cell.y + 50.0, text_width, 17.0),
                        item.description,
                        11.0,
                        _MUTED if not item.disabled else _DISABLED,
                        4,
                    )
                )
            return node

        center_x = cell.x + self._item_extent * 0.5
        marker_x = center_x - self._marker_size * 0.5
        marker_y = self.bounds.y + 30.0 - self._marker_size * 0.5
        text_width = max(0.0, cell.width - 12.0)
        node.add(self._marker_node(index, item, marker_x, marker_y, selected))
        node.add(
            self._text_node(
                f"{self.key}:item:{index}:time",
                Rect(cell.x + 6.0, cell.y + 6.0, text_width, 15.0),
                item.timestamp,
                10.0,
                _MUTED if not item.disabled else _DISABLED,
                4,
            )
        )
        node.add(
            self._text_node(
                f"{self.key}:item:{index}:title",
                Rect(cell.x + 6.0, cell.y + 44.0, text_width, 20.0),
                item.title,
                12.0,
                _FOREGROUND if not item.disabled else _DISABLED,
                4,
            )
        )
        return node

    def _marker_node(
        self,
        index: int,
        item: TimelineItem,
        x: float,
        y: float,
        selected: bool,
    ) -> SceneNode:
        color = _DISABLED if item.disabled else _ACCENT if selected else _AXIS
        return SceneNode(
            key=f"{self.key}:item:{index}:marker",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(x, y, self._marker_size, self._marker_size),
            fill=color,
            corner_radius=CornerRadius.uniform(self._marker_size * 0.5),
            z_index=5,
            hit_testable=False,
        )

    def _text_node(
        self,
        key: str,
        bounds: Rect,
        text: str,
        font_size: float,
        color: Color,
        z_index: int,
    ) -> SceneNode:
        return SceneNode(
            key=key,
            kind=SceneNodeKind.TEXT,
            bounds=bounds,
            fill=color,
            text=text,
            font_size=font_size,
            font_family=self._font_family,
            z_index=z_index,
            hit_testable=False,
        )

    def _sync_accessibility_value(self) -> None:
        item = self.selected_item
        index = self._selected_index
        if item is None or index is None:
            self.accessible_value_text = f"No timeline item selected of {len(self._items)}"
            return
        self.accessible_value_text = (
            f"{item.title}, {item.timestamp}, item {index + 1} of {len(self._items)}"
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
        ):
            return
        if self._orientation is TimelineOrientation.VERTICAL:
            index = int((platform_event.y - self.bounds.y) // self._item_extent)
        else:
            index = int((platform_event.x - self.bounds.x) // self._item_extent)
        if 0 <= index < len(self._items) and not self._items[index].disabled:
            self.select_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._items:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        key_code = platform_event.key_code
        if key_code in {_VK_RETURN, _VK_SPACE}:
            self.activate_selected()
            event.prevent_default()
            return
        target = self._navigation_target(key_code)
        if target is None:
            return
        self.select_index(target)
        event.prevent_default()

    def _navigation_target(self, key_code: int | None) -> int | None:
        if key_code == _VK_HOME:
            return self._first_enabled_index()
        if key_code == _VK_END:
            return self._last_enabled_index()
        if self._orientation is TimelineOrientation.VERTICAL:
            if key_code not in {_VK_UP, _VK_DOWN}:
                return None
            step = -1 if key_code == _VK_UP else 1
        else:
            if key_code not in {_VK_LEFT, _VK_RIGHT}:
                return None
            step = -1 if key_code == _VK_LEFT else 1

        if self._selected_index is None:
            return self._first_enabled_index()
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
            raise KeyError(f"Unknown selected timeline key: {selected_key!r}")
        if self._items[index].disabled:
            raise ValueError("selected_key cannot refer to a disabled timeline item.")
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
            raise IndexError("Timeline index is out of range.")
        return normalized

    @staticmethod
    def _semantic_description(item: TimelineItem) -> str:
        if item.description is None:
            return item.timestamp
        return f"{item.timestamp}. {item.description}"

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_items(items: Sequence[TimelineItem]) -> tuple[TimelineItem, ...]:
        normalized = tuple(items)
        keys: set[Hashable] = set()
        for item in normalized:
            if not isinstance(item, TimelineItem):
                raise TypeError("Timeline items must be TimelineItem values.")
            if item.key in keys:
                raise ValueError(f"Duplicate timeline key: {item.key!r}")
            keys.add(item.key)
        return normalized

    @staticmethod
    def _positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and positive.")
        return normalized
