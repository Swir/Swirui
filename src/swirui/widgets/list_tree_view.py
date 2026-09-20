"""Virtualized professional ListView and TreeView widgets."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

ListViewSelectionMode = Literal["single", "multiple"]

_VK_SPACE = 0x20
_VK_A = 0x41
_VK_HOME = 0x24
_VK_END = 0x23
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_DEFAULT_BACKGROUND = Color.from_hex("#07111C")
_DEFAULT_ROW_BACKGROUND = Color.from_hex("#081723")
_DEFAULT_ALTERNATE_ROW_BACKGROUND = Color.from_hex("#0A1A28")
_DEFAULT_SELECTED_BACKGROUND = Color.from_hex("#0B4F77")
_DEFAULT_FOREGROUND = Color.from_hex("#DDF5FF")
_DEFAULT_SECONDARY = Color.from_hex("#8DA8B8")


@dataclass(frozen=True, slots=True)
class ListItem:
    """Immutable ListView item with stable application identity."""

    key: Hashable
    label: str
    secondary: str | None = None
    disabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("ListItem.key must be hashable.")
        if not self.label.strip():
            raise ValueError("ListItem.label must not be empty.")


@dataclass(frozen=True, slots=True)
class TreeNode:
    """Immutable retained tree node with stable application identity."""

    key: Hashable
    label: str
    children: tuple[TreeNode, ...] = ()
    disabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("TreeNode.key must be hashable.")
        if not self.label.strip():
            raise ValueError("TreeNode.label must not be empty.")
        object.__setattr__(self, "children", tuple(self.children))


@dataclass(frozen=True, slots=True)
class _TreeRow:
    node: TreeNode
    depth: int
    parent_key: Hashable | None


class ListView(Widget):
    """Focusable retained list with stable-key selection and row virtualization."""

    def __init__(
        self,
        items: Sequence[ListItem],
        *,
        bounds: Rect,
        key: str | None = None,
        item_height: float = 40.0,
        cell_padding: float = 10.0,
        font_size: float = 14.0,
        font_family: str = "Segoe UI",
        corner_radius: float = 8.0,
        background: Color | None = None,
        row_background: Color | None = None,
        alternate_row_background: Color | None = None,
        selected_background: Color | None = None,
        foreground: Color | None = None,
        secondary_foreground: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "List",
        accessible_description: str | None = None,
        selection_mode: ListViewSelectionMode = "single",
    ) -> None:
        normalized_mode = str(selection_mode).strip().lower()
        if normalized_mode not in {"single", "multiple"}:
            raise ValueError("ListView selection_mode must be 'single' or 'multiple'.")
        self._selection_mode = cast(ListViewSelectionMode, normalized_mode)
        self._items = self._validate_items(items)
        self._item_height = self._validate_positive(item_height, "item_height")
        self._cell_padding = self._validate_non_negative(cell_padding, "cell_padding")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = str(font_family).strip()
        if not self._font_family:
            raise ValueError("font_family must not be empty.")
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._background = background or _DEFAULT_BACKGROUND
        self._row_background = row_background or _DEFAULT_ROW_BACKGROUND
        self._alternate_row_background = (
            alternate_row_background or _DEFAULT_ALTERNATE_ROW_BACKGROUND
        )
        self._selected_background = selected_background or _DEFAULT_SELECTED_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._secondary_foreground = secondary_foreground or _DEFAULT_SECONDARY
        self._selected_keys: set[Hashable] = set()
        self._selected_index: int | None = None
        self._selection_anchor: int | None = None
        self._scroll_offset = 0.0

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
    def items(self) -> tuple[ListItem, ...]:
        return self._items

    @property
    def selection_mode(self) -> ListViewSelectionMode:
        return self._selection_mode

    @property
    def selected_indices(self) -> tuple[int, ...]:
        return tuple(
            index for index, item in enumerate(self._items) if item.key in self._selected_keys
        )

    @property
    def selected_items(self) -> tuple[ListItem, ...]:
        return tuple(self._items[index] for index in self.selected_indices)

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_item(self) -> ListItem | None:
        if self._selected_index is None:
            return None
        return self._items[self._selected_index]

    @property
    def scroll_offset(self) -> float:
        return min(self._scroll_offset, self._max_scroll_offset())

    @property
    def visible_item_range(self) -> range:
        if not self._items or self.bounds.height <= 0.0:
            return range(0)
        offset = self.scroll_offset
        first = min(len(self._items) - 1, int(offset // self._item_height))
        partial = offset - (first * self._item_height)
        count = max(1, math.ceil((self.bounds.height + partial) / self._item_height))
        return range(first, min(len(self._items), first + count))

    def set_items(self, items: Sequence[ListItem]) -> ListView:
        """Replace items while preserving selection by stable item key."""

        normalized = self._validate_items(items)
        if normalized == self._items:
            return self
        primary_key = None if self.selected_item is None else self.selected_item.key
        anchor_key = self._key_at_index(self._selection_anchor)
        self._items = normalized
        available = {item.key for item in normalized}
        self._selected_keys.intersection_update(available)
        self._selected_index = self._index_for_key(primary_key)
        if self._selected_index is None and self._selected_keys:
            self._selected_index = next(
                index for index, item in enumerate(normalized) if item.key in self._selected_keys
            )
        self._selection_anchor = self._index_for_key(anchor_key)
        if self._selection_anchor is None:
            self._selection_anchor = self._selected_index
        self._scroll_offset = min(self._scroll_offset, self._max_scroll_offset())
        self._sync_accessibility_value()
        self.invalidate(reason="items")
        return self

    def select_index(
        self,
        index: int | None,
        *,
        ensure_visible: bool = True,
        extend: bool = False,
        toggle: bool = False,
    ) -> ListView:
        """Select one row, optionally extending/toggling in multiple mode."""

        normalized = self._normalize_optional_index(index)
        if self._selection_mode == "single":
            extend = False
            toggle = False

        if normalized is None:
            selected_keys: set[Hashable] = set()
            primary = None
            anchor = None
        elif self._items[normalized].disabled:
            return self
        elif extend:
            anchor = self._selection_anchor
            if anchor is None:
                anchor = self._selected_index if self._selected_index is not None else normalized
            start, stop = sorted((anchor, normalized))
            selected_keys = {
                self._items[item_index].key
                for item_index in range(start, stop + 1)
                if not self._items[item_index].disabled
            }
            primary = (
                normalized
                if self._items[normalized].key in selected_keys
                else self._selected_index
            )
        elif toggle:
            selected_keys = set(self._selected_keys)
            item_key = self._items[normalized].key
            if item_key in selected_keys:
                selected_keys.remove(item_key)
                primary = self._nearest_selected_index(normalized, selected_keys)
            else:
                selected_keys.add(item_key)
                primary = normalized
            anchor = normalized
        else:
            selected_keys = {self._items[normalized].key}
            primary = normalized
            anchor = normalized

        return self._apply_selection(
            selected_keys,
            primary_index=primary,
            anchor_index=anchor,
            ensure_visible=ensure_visible,
        )

    def select_indices(
        self,
        indices: Sequence[int],
        *,
        primary_index: int | None = None,
        ensure_visible: bool = True,
    ) -> ListView:
        normalized = tuple(
            dict.fromkeys(self._normalize_required_index(index) for index in indices)
        )
        if self._selection_mode == "single" and len(normalized) > 1:
            raise ValueError("ListView single selection mode accepts at most one item.")
        enabled = tuple(index for index in normalized if not self._items[index].disabled)
        if not enabled:
            return self.clear_selection()
        primary = (
            enabled[0]
            if primary_index is None
            else self._normalize_required_index(primary_index)
        )
        if primary not in enabled:
            raise ValueError("primary_index must reference an enabled selected item.")
        return self._apply_selection(
            {self._items[index].key for index in enabled},
            primary_index=primary,
            anchor_index=primary,
            ensure_visible=ensure_visible,
        )

    def select_all(self) -> ListView:
        if self._selection_mode != "multiple":
            raise ValueError("ListView select_all requires selection_mode='multiple'.")
        enabled = {item.key for item in self._items if not item.disabled}
        if not enabled:
            return self.clear_selection()
        primary = self._selected_index
        if primary is None or self._items[primary].key not in enabled:
            primary = next(
                index for index, item in enumerate(self._items) if item.key in enabled
            )
        return self._apply_selection(
            enabled,
            primary_index=primary,
            anchor_index=primary,
            ensure_visible=False,
        )

    def clear_selection(self) -> ListView:
        return self._apply_selection(
            set(),
            primary_index=None,
            anchor_index=None,
            ensure_visible=False,
        )

    def scroll_by(self, delta: float) -> ListView:
        normalized = float(delta)
        if not math.isfinite(normalized):
            raise ValueError("ListView scroll delta must be finite.")
        return self._set_scroll_offset(self._scroll_offset + normalized)

    def scroll_to_index(self, index: int) -> ListView:
        normalized = self._normalize_required_index(index)
        item_top = normalized * self._item_height
        item_bottom = item_top + self._item_height
        offset = self.scroll_offset
        if item_top < offset:
            return self._set_scroll_offset(item_top)
        if item_bottom > offset + self.bounds.height:
            return self._set_scroll_offset(item_bottom - self.bounds.height)
        return self

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
        offset = self.scroll_offset
        for index in self.visible_item_range:
            item = self._items[index]
            y = self.bounds.y + (index * self._item_height) - offset
            row_bounds = Rect(self.bounds.x, y, self.bounds.width, self._item_height)
            selected = item.key in self._selected_keys
            fill = (
                self._selected_background
                if selected
                else self._alternate_row_background
                if index % 2
                else self._row_background
            )
            row = SceneNode(
                key=f"{self.key}:row:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row_bounds,
                fill=fill,
                z_index=1,
                clip_to_bounds=True,
                hit_testable=False,
            )
            prefix = self._row_prefix(index)
            indent = self._row_indent(index)
            label_bounds = Rect(
                row_bounds.x + self._cell_padding + indent,
                row_bounds.y,
                max(0.0, row_bounds.width - (2.0 * self._cell_padding) - indent),
                row_bounds.height,
            )
            row.add(
                self._text_node(
                    key=f"{self.key}:row:{index}:label",
                    bounds=label_bounds,
                    text=f"{prefix}{item.label}",
                    color=self._foreground if not item.disabled else self._secondary_foreground,
                    font_size=self._font_size,
                )
            )
            if item.secondary:
                secondary_width = min(
                    max(80.0, row_bounds.width * 0.35),
                    max(0.0, row_bounds.width - 2.0 * self._cell_padding),
                )
                secondary_bounds = Rect(
                    row_bounds.x + row_bounds.width - secondary_width - self._cell_padding,
                    row_bounds.y,
                    secondary_width,
                    row_bounds.height,
                )
                row.add(
                    self._text_node(
                        key=f"{self.key}:row:{index}:secondary",
                        bounds=secondary_bounds,
                        text=item.secondary,
                        color=self._secondary_foreground,
                        font_size=max(10.0, self._font_size - 1.0),
                    )
                )
            root.add(row)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        selected = self._selected_keys
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:item:{index}",
                role=AccessibilityRole.LIST_ITEM,
                name=self._items[index].label,
                description=self._accessibility_description(index),
                enabled=self.enabled and not self._items[index].disabled,
                focusable=False,
                focused=False,
                selected=self._items[index].key in selected,
                active=bool(focused is self and index == self._selected_index),
                row_index=index,
            )
            for index in self.visible_item_range
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
            children=children,
            row_count=len(self._items),
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
            or not self._contains_point(platform_event.x, platform_event.y)
        ):
            return
        content_y = platform_event.y - self.bounds.y + self.scroll_offset
        index = int(content_y // self._item_height)
        if not 0 <= index < len(self._items):
            return
        if self._handle_disclosure_pointer(index, platform_event.x):
            event.prevent_default()
            return
        self.select_index(
            index,
            ensure_visible=False,
            extend=bool(platform_event.shift),
            toggle=bool(platform_event.ctrl or platform_event.meta),
        )
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._items:
            return
        if self._handle_special_key(platform_event):
            event.prevent_default()
            return
        if platform_event.alt or platform_event.meta:
            return
        if (
            self._selection_mode == "multiple"
            and platform_event.ctrl
            and platform_event.key_code == _VK_A
        ):
            self.select_all()
            event.prevent_default()
            return
        if (
            self._selection_mode == "multiple"
            and platform_event.ctrl
            and platform_event.key_code == _VK_SPACE
            and self._selected_index is not None
        ):
            self.select_index(self._selected_index, toggle=True)
            event.prevent_default()
            return
        if platform_event.ctrl:
            return

        target = self._navigation_target(platform_event.key_code)
        if target is None:
            return
        self.select_index(
            target,
            ensure_visible=True,
            extend=bool(platform_event.shift and self._selection_mode == "multiple"),
        )
        event.prevent_default()

    def _navigation_target(self, key_code: int | None) -> int | None:
        current = self._selected_index
        if key_code == _VK_HOME:
            candidate = 0
        elif key_code == _VK_END:
            candidate = len(self._items) - 1
        elif key_code == _VK_UP:
            candidate = 0 if current is None else max(0, current - 1)
        elif key_code == _VK_DOWN:
            candidate = 0 if current is None else min(len(self._items) - 1, current + 1)
        elif key_code in (_VK_PRIOR, _VK_NEXT):
            page = max(1, int(self.bounds.height // self._item_height))
            origin = 0 if current is None else current
            direction = -1 if key_code == _VK_PRIOR else 1
            candidate = min(len(self._items) - 1, max(0, origin + direction * page))
        else:
            return None
        return self._nearest_enabled_index(candidate, -1 if key_code in (_VK_UP, _VK_PRIOR) else 1)

    def _nearest_enabled_index(self, origin: int, direction: int) -> int | None:
        if not self._items:
            return None
        index = min(max(0, origin), len(self._items) - 1)
        while 0 <= index < len(self._items):
            if not self._items[index].disabled:
                return index
            index += direction
        return None

    def _apply_selection(
        self,
        selected_keys: set[Hashable],
        *,
        primary_index: int | None,
        anchor_index: int | None,
        ensure_visible: bool,
    ) -> ListView:
        old_keys = self._selected_keys
        old_primary = self._selected_index
        if primary_index is not None:
            primary_index = self._normalize_required_index(primary_index)
            if self._items[primary_index].key not in selected_keys:
                raise ValueError("ListView primary selection must be selected.")
        changed = selected_keys != old_keys or primary_index != old_primary
        self._selected_keys = set(selected_keys)
        self._selected_index = primary_index
        self._selection_anchor = anchor_index
        if primary_index is not None and ensure_visible:
            self.scroll_to_index(primary_index)
        self._sync_accessibility_value()
        if not changed:
            return self
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=primary_index,
            item=None if primary_index is None else self._items[primary_index],
            indices=self.selected_indices,
            items=self.selected_items,
        )
        return self

    def _set_scroll_offset(self, value: float) -> ListView:
        normalized = min(max(0.0, float(value)), self._max_scroll_offset())
        if normalized == self._scroll_offset:
            return self
        self._scroll_offset = normalized
        self.invalidate(reason="scroll_offset")
        return self

    def _max_scroll_offset(self) -> float:
        return max(0.0, len(self._items) * self._item_height - self.bounds.height)

    def _text_node(
        self,
        *,
        key: str,
        bounds: Rect,
        text: str,
        color: Color,
        font_size: float,
    ) -> SceneNode:
        line_height = min(bounds.height, font_size * 1.35)
        y = bounds.y + max(0.0, (bounds.height - line_height) * 0.5)
        return SceneNode(
            key=key,
            kind=SceneNodeKind.TEXT,
            bounds=Rect(bounds.x, y, bounds.width, line_height),
            fill=color,
            text=text,
            font_size=font_size,
            font_family=self._font_family,
            z_index=2,
            hit_testable=False,
        )

    def _row_indent(self, index: int) -> float:
        _ = index
        return 0.0

    def _row_prefix(self, index: int) -> str:
        _ = index
        return ""

    def _accessibility_description(self, index: int) -> str | None:
        return self._items[index].secondary

    def _handle_disclosure_pointer(self, index: int, x: float) -> bool:
        _ = index, x
        return False

    def _handle_special_key(self, platform_event: PlatformEvent) -> bool:
        _ = platform_event
        return False

    def _key_at_index(self, index: int | None) -> Hashable | None:
        if index is None or not 0 <= index < len(self._items):
            return None
        return self._items[index].key

    def _index_for_key(self, key: Hashable | None) -> int | None:
        if key is None:
            return None
        for index, item in enumerate(self._items):
            if item.key == key:
                return index
        return None

    def _nearest_selected_index(
        self,
        origin: int,
        selected_keys: set[Hashable],
    ) -> int | None:
        candidates = [
            index for index, item in enumerate(self._items) if item.key in selected_keys
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda index: (abs(index - origin), index))

    def _normalize_optional_index(self, index: int | None) -> int | None:
        if index is None:
            return None
        return self._normalize_required_index(index)

    def _normalize_required_index(self, index: int) -> int:
        normalized = int(index)
        if not 0 <= normalized < len(self._items):
            raise IndexError("ListView item index is out of range.")
        return normalized

    def _sync_accessibility_value(self) -> None:
        count = len(self._selected_keys)
        noun = "item" if count == 1 else "items"
        self.accessible_value_text = f"{count} {noun} selected of {len(self._items)}"

    @staticmethod
    def _validate_items(items: Sequence[ListItem]) -> tuple[ListItem, ...]:
        normalized = tuple(items)
        seen: set[Hashable] = set()
        for item in normalized:
            if item.key in seen:
                raise ValueError(
                    f"ListView item keys must be unique; duplicate {item.key!r}."
                )
            seen.add(item.key)
        return normalized

    def _contains_point(self, x: float, y: float) -> bool:
        return (
            self.bounds.x <= x < self.bounds.x + self.bounds.width
            and self.bounds.y <= y < self.bounds.y + self.bounds.height
        )

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

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


class TreeView(ListView):
    """Virtualized retained tree with stable-key selection and expansion state."""

    def __init__(
        self,
        nodes: Sequence[TreeNode],
        *,
        bounds: Rect,
        key: str | None = None,
        expanded_keys: Sequence[Hashable] = (),
        indent_width: float = 20.0,
        item_height: float = 40.0,
        cell_padding: float = 10.0,
        font_size: float = 14.0,
        font_family: str = "Segoe UI",
        corner_radius: float = 8.0,
        background: Color | None = None,
        row_background: Color | None = None,
        alternate_row_background: Color | None = None,
        selected_background: Color | None = None,
        foreground: Color | None = None,
        secondary_foreground: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Tree",
        accessible_description: str | None = None,
        selection_mode: ListViewSelectionMode = "single",
    ) -> None:
        self._nodes = tuple(nodes)
        self._validate_tree(self._nodes)
        self._expanded_keys = set(expanded_keys)
        self._indent_width = self._validate_positive(indent_width, "indent_width")
        self._tree_rows = self._flatten(self._nodes)
        super().__init__(
            self._list_items(self._tree_rows),
            bounds=bounds,
            key=key,
            item_height=item_height,
            cell_padding=cell_padding,
            font_size=font_size,
            font_family=font_family,
            corner_radius=corner_radius,
            background=background,
            row_background=row_background,
            alternate_row_background=alternate_row_background,
            selected_background=selected_background,
            foreground=foreground,
            secondary_foreground=secondary_foreground,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            selection_mode=selection_mode,
        )

    @property
    def nodes(self) -> tuple[TreeNode, ...]:
        return self._nodes

    @property
    def expanded_keys(self) -> frozenset[Hashable]:
        return frozenset(self._expanded_keys)

    @property
    def selected_node(self) -> TreeNode | None:
        selected = self.selected_item
        if selected is None:
            return None
        row = self._tree_row_for_key(selected.key)
        return None if row is None else row.node

    def set_nodes(self, nodes: Sequence[TreeNode]) -> TreeView:
        normalized = tuple(nodes)
        self._validate_tree(normalized)
        known = self._collect_keys(normalized)
        self._expanded_keys.intersection_update(known)
        self._nodes = normalized
        self._refresh_tree_rows()
        return self

    def expand(self, key: Hashable) -> TreeView:
        row = self._required_tree_row(key)
        if not row.node.children or key in self._expanded_keys:
            return self
        self._expanded_keys.add(key)
        self._refresh_tree_rows()
        self.emit("expanded", key=key, node=row.node)
        return self

    def collapse(self, key: Hashable) -> TreeView:
        row = self._required_tree_row(key)
        if key not in self._expanded_keys:
            return self
        self._expanded_keys.remove(key)
        self._refresh_tree_rows()
        self.emit("collapsed", key=key, node=row.node)
        return self

    def toggle_expanded(self, key: Hashable) -> TreeView:
        return self.collapse(key) if key in self._expanded_keys else self.expand(key)

    def _refresh_tree_rows(self) -> None:
        self._tree_rows = self._flatten(self._nodes)
        super().set_items(self._list_items(self._tree_rows))
        self.invalidate(reason="tree_rows")

    def _row_indent(self, index: int) -> float:
        return self._tree_rows[index].depth * self._indent_width

    def _row_prefix(self, index: int) -> str:
        row = self._tree_rows[index]
        if not row.node.children:
            return "  "
        return "▾ " if row.node.key in self._expanded_keys else "▸ "

    def _accessibility_description(self, index: int) -> str | None:
        row = self._tree_rows[index]
        state = ""
        if row.node.children:
            state = ", expanded" if row.node.key in self._expanded_keys else ", collapsed"
        return f"Level {row.depth + 1}{state}"

    def _handle_disclosure_pointer(self, index: int, x: float) -> bool:
        row = self._tree_rows[index]
        if not row.node.children:
            return False
        disclosure_x = self.bounds.x + self._cell_padding + self._row_indent(index)
        if disclosure_x <= x < disclosure_x + self._indent_width:
            self.toggle_expanded(row.node.key)
            return True
        return False

    def _handle_special_key(self, platform_event: PlatformEvent) -> bool:
        if self.selected_index is None or platform_event.ctrl or platform_event.alt:
            return False
        row = self._tree_rows[self.selected_index]
        if platform_event.key_code == _VK_RIGHT:
            if row.node.children and row.node.key not in self._expanded_keys:
                self.expand(row.node.key)
                return True
            if row.node.children:
                child_key = row.node.children[0].key
                child_index = self._index_for_key(child_key)
                if child_index is not None:
                    self.select_index(child_index)
                    return True
        if platform_event.key_code == _VK_LEFT:
            if row.node.key in self._expanded_keys:
                self.collapse(row.node.key)
                return True
            parent_index = self._index_for_key(row.parent_key)
            if parent_index is not None:
                self.select_index(parent_index)
                return True
        return False

    def _flatten(
        self,
        nodes: Sequence[TreeNode],
        *,
        depth: int = 0,
        parent_key: Hashable | None = None,
    ) -> tuple[_TreeRow, ...]:
        rows: list[_TreeRow] = []
        for node in nodes:
            rows.append(_TreeRow(node=node, depth=depth, parent_key=parent_key))
            if node.children and node.key in self._expanded_keys:
                rows.extend(
                    self._flatten(
                        node.children,
                        depth=depth + 1,
                        parent_key=node.key,
                    )
                )
        return tuple(rows)

    @staticmethod
    def _list_items(rows: Sequence[_TreeRow]) -> tuple[ListItem, ...]:
        return tuple(
            ListItem(key=row.node.key, label=row.node.label, disabled=row.node.disabled)
            for row in rows
        )

    def _tree_row_for_key(self, key: Hashable) -> _TreeRow | None:
        for row in self._tree_rows:
            if row.node.key == key:
                return row
        return None

    def _required_tree_row(self, key: Hashable) -> _TreeRow:
        row = self._find_tree_row(self._nodes, key)
        if row is None:
            raise KeyError(f"Unknown TreeView node key: {key!r}")
        return row

    def _find_tree_row(
        self,
        nodes: Sequence[TreeNode],
        key: Hashable,
        *,
        depth: int = 0,
        parent_key: Hashable | None = None,
    ) -> _TreeRow | None:
        for node in nodes:
            if node.key == key:
                return _TreeRow(node=node, depth=depth, parent_key=parent_key)
            found = self._find_tree_row(
                node.children,
                key,
                depth=depth + 1,
                parent_key=node.key,
            )
            if found is not None:
                return found
        return None

    @classmethod
    def _validate_tree(cls, nodes: Sequence[TreeNode]) -> None:
        seen: set[Hashable] = set()

        def visit(current: Sequence[TreeNode]) -> None:
            for node in current:
                if node.key in seen:
                    raise ValueError(
                        f"TreeView node keys must be globally unique; duplicate {node.key!r}."
                    )
                seen.add(node.key)
                visit(node.children)

        visit(nodes)

    @classmethod
    def _collect_keys(cls, nodes: Sequence[TreeNode]) -> set[Hashable]:
        keys: set[Hashable] = set()
        for node in nodes:
            keys.add(node.key)
            keys.update(cls._collect_keys(node.children))
        return keys
