"""Retained context-menu and command-palette widgets for SwirUI applications."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .command_surfaces import CommandItem

_VK_BACK = 0x08
_VK_ESCAPE = 0x1B
_VK_END = 0x23
_VK_HOME = 0x24
_VK_UP = 0x26
_VK_DOWN = 0x28
_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_DELETE = 0x2E

_BACKGROUND = Color.from_hex("#06101A")
_ROW_BACKGROUND = Color.from_hex("#081723")
_ACTIVE_BACKGROUND = Color.from_hex("#0B3550")
_INPUT_BACKGROUND = Color.from_hex("#04111B")
_FOREGROUND = Color.from_hex("#DDF5FF")
_MUTED = Color.from_hex("#8DA8B8")
_ACCENT = Color.from_hex("#23C9FF")


class ContextMenu(Widget):
    """Retained popup command menu with stable-key selection and keyboard navigation."""

    def __init__(
        self,
        items: Sequence[CommandItem],
        *,
        bounds: Rect,
        key: str | None = None,
        row_height: float = 38.0,
        dismiss_on_invoke: bool = True,
        opacity: float = 1.0,
        z_index: int = 100,
        accessible_name: str = "Context menu",
        accessible_description: str | None = None,
    ) -> None:
        self._items = _validate_items(items)
        self._row_height = _positive(row_height, "row_height")
        self._dismiss_on_invoke = bool(dismiss_on_invoke)
        self._active_index = _first_enabled(self._items)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.MENU,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self._sync_accessibility()

    @property
    def items(self) -> tuple[CommandItem, ...]:
        return self._items

    @property
    def active_index(self) -> int | None:
        return self._active_index

    @property
    def active_item(self) -> CommandItem | None:
        if self._active_index is None:
            return None
        return self._items[self._active_index]

    def set_items(self, items: Sequence[CommandItem]) -> ContextMenu:
        normalized = _validate_items(items)
        if normalized == self._items:
            return self
        active_key = None if self.active_item is None else self.active_item.key
        self._items = normalized
        self._active_index = _index_for_key(normalized, active_key)
        if self._active_index is None or self._items[self._active_index].disabled:
            self._active_index = _first_enabled(normalized)
        self._sync_accessibility()
        self.invalidate(reason="items")
        return self

    def open_at(self, x: float, y: float) -> ContextMenu:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Context menu coordinates must be finite.")
        self.bounds = Rect(float(x), float(y), self.bounds.width, self.bounds.height)
        self.visible = True
        return self

    def close(self) -> ContextMenu:
        self.visible = False
        self.emit("dismissed")
        return self

    def activate_key(self, key: Hashable) -> ContextMenu:
        index = _index_for_key(self._items, key)
        if index is None:
            raise KeyError(f"Unknown context-menu command key: {key!r}")
        return self._activate_index(index)

    def row_bounds(self, index: int) -> Rect:
        normalized = _normalize_index(index, len(self._items), "Context-menu row")
        return Rect(
            self.bounds.x,
            self.bounds.y + normalized * self._row_height,
            self.bounds.width,
            min(
                self._row_height,
                max(0.0, self.bounds.bottom - (self.bounds.y + normalized * self._row_height)),
            ),
        )

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_BACKGROUND,
            corner_radius=CornerRadius.uniform(10.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        if not self.visible:
            root.opacity = 0.0
            root.hit_testable = False
            return root
        for index, item in enumerate(self._items):
            row = self.row_bounds(index)
            if row.height <= 0.0 or row.y >= self.bounds.bottom:
                break
            active = index == self._active_index
            node = SceneNode(
                key=f"{self.key}:item:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row,
                fill=_ACTIVE_BACKGROUND if active else _ROW_BACKGROUND,
                z_index=1,
                hit_testable=False,
            )
            _add_command_text(node, self.key, "item", index, row, item)
            if active:
                _add_active_accent(node, self.key, "item", index, row)
            root.add(node)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:item:{index}",
                role=AccessibilityRole.MENU_ITEM,
                name=item.label,
                description=item.shortcut,
                enabled=self.enabled and not item.disabled,
                focusable=False,
                focused=False,
                selected=index == self._active_index,
                active=index == self._active_index,
            )
            for index, item in enumerate(self._items)
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.MENU,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=children,
        )

    def _activate_index(self, index: int) -> ContextMenu:
        normalized = _normalize_index(index, len(self._items), "Context-menu row")
        item = self._items[normalized]
        if item.disabled:
            return self
        self._active_index = normalized
        self._sync_accessibility()
        self.invalidate(reason="selection")
        self.emit("command_invoked", index=normalized, key=item.key, item=item)
        if self._dismiss_on_invoke:
            self.close()
        return self

    def _sync_accessibility(self) -> None:
        active = self.active_item
        if active is None:
            self.accessible_value_text = f"No active command of {len(self._items)}"
            return
        index = self._active_index
        assert index is not None
        self.accessible_value_text = f"{active.label}, command {index + 1} of {len(self._items)}"

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or not self.visible
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
        index = int((platform_event.y - self.bounds.y) // self._row_height)
        if 0 <= index < len(self._items):
            self._activate_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or not self.visible or platform_event is None:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        key_code = platform_event.key_code
        if key_code == _VK_ESCAPE:
            self.close()
            event.prevent_default()
            return
        if key_code in {_VK_RETURN, _VK_SPACE} and self._active_index is not None:
            self._activate_index(self._active_index)
            event.prevent_default()
            return
        target = _navigation_target(self._items, self._active_index, key_code)
        if target is None:
            return
        self._active_index = target
        self._sync_accessibility()
        self.invalidate(reason="selection")
        event.prevent_default()


class CommandPalette(Widget):
    """Searchable retained command palette with native text-input and keyboard routing."""

    def __init__(
        self,
        items: Sequence[CommandItem],
        *,
        bounds: Rect,
        key: str | None = None,
        query: str = "",
        header_height: float = 48.0,
        row_height: float = 40.0,
        max_visible_rows: int = 8,
        dismiss_on_invoke: bool = True,
        opacity: float = 1.0,
        z_index: int = 110,
        accessible_name: str = "Command palette",
        accessible_description: str | None = None,
    ) -> None:
        self._items = _validate_items(items)
        self._header_height = _positive(header_height, "header_height")
        self._row_height = _positive(row_height, "row_height")
        self._max_visible_rows = int(max_visible_rows)
        if self._max_visible_rows <= 0:
            raise ValueError("max_visible_rows must be positive.")
        self._dismiss_on_invoke = bool(dismiss_on_invoke)
        self._query = _normalize_query(query)
        self._filtered = _filter_items(self._items, self._query)
        self._active_index = _first_enabled(self._filtered)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.DIALOG,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self.on("text_input", self._on_text_input)
        self._sync_accessibility()

    @property
    def items(self) -> tuple[CommandItem, ...]:
        return self._items

    @property
    def query(self) -> str:
        return self._query

    @property
    def filtered_items(self) -> tuple[CommandItem, ...]:
        return self._filtered

    @property
    def active_index(self) -> int | None:
        return self._active_index

    @property
    def active_item(self) -> CommandItem | None:
        if self._active_index is None:
            return None
        return self._filtered[self._active_index]

    def set_items(self, items: Sequence[CommandItem]) -> CommandPalette:
        normalized = _validate_items(items)
        if normalized == self._items:
            return self
        active_key = None if self.active_item is None else self.active_item.key
        self._items = normalized
        self._apply_filter(active_key=active_key, reason="items")
        return self

    def set_query(self, query: str) -> CommandPalette:
        normalized = _normalize_query(query)
        if normalized == self._query:
            return self
        active_key = None if self.active_item is None else self.active_item.key
        self._query = normalized
        self._apply_filter(active_key=active_key, reason="query")
        self.emit("query_changed", query=self._query, result_count=len(self._filtered))
        return self

    def clear_query(self) -> CommandPalette:
        return self.set_query("")

    def activate_key(self, key: Hashable) -> CommandPalette:
        index = _index_for_key(self._filtered, key)
        if index is None:
            raise KeyError(f"Unknown visible command key: {key!r}")
        return self._activate_index(index)

    def row_bounds(self, index: int) -> Rect:
        normalized = _normalize_index(index, len(self._filtered), "Command-palette row")
        y = self.bounds.y + self._header_height + normalized * self._row_height
        return Rect(
            self.bounds.x,
            y,
            self.bounds.width,
            min(self._row_height, max(0.0, self.bounds.bottom - y)),
        )

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_BACKGROUND,
            corner_radius=CornerRadius.uniform(12.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        header = Rect(
            self.bounds.x,
            self.bounds.y,
            self.bounds.width,
            min(self._header_height, self.bounds.height),
        )
        header_node = SceneNode(
            key=f"{self.key}:query",
            kind=SceneNodeKind.RECTANGLE,
            bounds=header,
            fill=_INPUT_BACKGROUND,
            z_index=1,
            hit_testable=False,
        )
        query_text = self._query if self._query else "Type a command..."
        header_node.add(
            SceneNode(
                key=f"{self.key}:query:text",
                kind=SceneNodeKind.TEXT,
                bounds=Rect(
                    header.x + 14.0,
                    header.y + 13.0,
                    max(0.0, header.width - 28.0),
                    22.0,
                ),
                fill=_FOREGROUND if self._query else _MUTED,
                text=query_text,
                font_size=15.0,
                font_family="Segoe UI",
                z_index=2,
                hit_testable=False,
            )
        )
        root.add(header_node)

        for index, item in enumerate(self._filtered[: self._max_visible_rows]):
            row = self.row_bounds(index)
            if row.height <= 0.0 or row.y >= self.bounds.bottom:
                break
            active = index == self._active_index
            node = SceneNode(
                key=f"{self.key}:result:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row,
                fill=_ACTIVE_BACKGROUND if active else _ROW_BACKGROUND,
                z_index=1,
                hit_testable=False,
            )
            _add_command_text(node, self.key, "result", index, row, item)
            if active:
                _add_active_accent(node, self.key, "result", index, row)
            root.add(node)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:result:{index}",
                role=AccessibilityRole.MENU_ITEM,
                name=item.label,
                description=item.shortcut,
                enabled=self.enabled and not item.disabled,
                focusable=False,
                focused=False,
                selected=index == self._active_index,
                active=index == self._active_index,
            )
            for index, item in enumerate(self._filtered[: self._max_visible_rows])
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.DIALOG,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=children,
        )

    def _activate_index(self, index: int) -> CommandPalette:
        normalized = _normalize_index(index, len(self._filtered), "Command-palette row")
        item = self._filtered[normalized]
        if item.disabled:
            return self
        self._active_index = normalized
        self._sync_accessibility()
        self.invalidate(reason="selection")
        self.emit("command_invoked", index=normalized, key=item.key, item=item)
        if self._dismiss_on_invoke:
            self.visible = False
            self.emit("dismissed")
        return self

    def _apply_filter(self, *, active_key: Hashable | None, reason: str) -> None:
        self._filtered = _filter_items(self._items, self._query)
        self._active_index = _index_for_key(self._filtered, active_key)
        if (
            self._active_index is None
            or self._filtered[self._active_index].disabled
            or self._active_index >= self._max_visible_rows
        ):
            self._active_index = _first_enabled(self._filtered[: self._max_visible_rows])
        self._sync_accessibility()
        self.invalidate(reason=reason)

    def _sync_accessibility(self) -> None:
        active = self.active_item
        result_count = len(self._filtered)
        if active is None:
            self.accessible_value_text = f"{result_count} matching commands; no active command"
            return
        index = self._active_index
        assert index is not None
        self.accessible_value_text = (
            f"{result_count} matching commands; {active.label}, result {index + 1}"
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or not self.visible
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
            or not (
                self.bounds.x <= platform_event.x < self.bounds.right
                and self.bounds.y <= platform_event.y < self.bounds.bottom
            )
            or platform_event.y < self.bounds.y + self._header_height
        ):
            return
        index = int(
            (platform_event.y - self.bounds.y - self._header_height) // self._row_height
        )
        if 0 <= index < min(len(self._filtered), self._max_visible_rows):
            self._activate_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or not self.visible or platform_event is None:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        key_code = platform_event.key_code
        if key_code == _VK_ESCAPE:
            self.visible = False
            self.emit("dismissed")
            event.prevent_default()
            return
        if key_code in {_VK_BACK, _VK_DELETE} and self._query:
            self.set_query(self._query[:-1])
            event.prevent_default()
            return
        if key_code == _VK_RETURN and self._active_index is not None:
            self._activate_index(self._active_index)
            event.prevent_default()
            return
        visible = self._filtered[: self._max_visible_rows]
        target = _navigation_target(visible, self._active_index, key_code)
        if target is None:
            return
        self._active_index = target
        self._sync_accessibility()
        self.invalidate(reason="selection")
        event.prevent_default()

    def _on_text_input(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.TEXT_INPUT)
        if not self.enabled or not self.visible or platform_event is None:
            return
        text = platform_event.text
        if not text or any(character in "\r\n\t" for character in text):
            return
        self.set_query(self._query + text)
        event.prevent_default()


def _add_command_text(
    node: SceneNode,
    root_key: str,
    kind: str,
    index: int,
    row: Rect,
    item: CommandItem,
) -> None:
    node.add(
        SceneNode(
            key=f"{root_key}:{kind}:{index}:label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(row.x + 14.0, row.y + 9.0, max(0.0, row.width - 28.0), 20.0),
            fill=_MUTED if item.disabled else _FOREGROUND,
            text=item.label,
            font_size=14.0,
            font_family="Segoe UI",
            z_index=3,
            hit_testable=False,
        )
    )
    if item.shortcut is not None:
        node.add(
            SceneNode(
                key=f"{root_key}:{kind}:{index}:shortcut",
                kind=SceneNodeKind.TEXT,
                bounds=Rect(
                    row.x + max(14.0, row.width - 116.0),
                    row.y + 10.0,
                    min(102.0, max(0.0, row.width - 28.0)),
                    18.0,
                ),
                fill=_MUTED,
                text=item.shortcut,
                font_size=11.0,
                font_family="Segoe UI",
                z_index=3,
                hit_testable=False,
            )
        )


def _add_active_accent(
    node: SceneNode,
    root_key: str,
    kind: str,
    index: int,
    row: Rect,
) -> None:
    node.add(
        SceneNode(
            key=f"{root_key}:{kind}:{index}:accent",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(row.x, row.y + 5.0, 3.0, max(0.0, row.height - 10.0)),
            fill=_ACCENT,
            z_index=4,
            hit_testable=False,
        )
    )


def _filter_items(
    items: Sequence[CommandItem],
    query: str,
) -> tuple[CommandItem, ...]:
    if not query:
        return tuple(items)
    tokens = tuple(token for token in query.casefold().split() if token)
    if not tokens:
        return tuple(items)
    matches = []
    for item in items:
        haystack = item.label.casefold()
        if item.shortcut is not None:
            haystack = f"{haystack} {item.shortcut.casefold()}"
        if all(token in haystack for token in tokens):
            matches.append(item)
    return tuple(matches)


def _normalize_query(query: str) -> str:
    if not isinstance(query, str):
        raise TypeError("CommandPalette query must be a string.")
    return " ".join(query.split())


def _validate_items(items: Sequence[CommandItem]) -> tuple[CommandItem, ...]:
    normalized = tuple(items)
    keys: set[Hashable] = set()
    for item in normalized:
        if not isinstance(item, CommandItem):
            raise TypeError("Context commands require CommandItem values.")
        if item.key in keys:
            raise ValueError(f"Duplicate command key: {item.key!r}")
        keys.add(item.key)
    return normalized


def _index_for_key(
    items: Sequence[CommandItem],
    key: Hashable | None,
) -> int | None:
    if key is None:
        return None
    return next((index for index, item in enumerate(items) if item.key == key), None)


def _first_enabled(items: Sequence[CommandItem]) -> int | None:
    return next((index for index, item in enumerate(items) if not item.disabled), None)


def _last_enabled(items: Sequence[CommandItem]) -> int | None:
    return next(
        (
            index
            for index in range(len(items) - 1, -1, -1)
            if not items[index].disabled
        ),
        None,
    )


def _next_enabled(
    items: Sequence[CommandItem],
    current: int | None,
    step: int,
) -> int | None:
    if not items:
        return None
    if current is None:
        return _first_enabled(items) if step > 0 else _last_enabled(items)
    index = current
    for _ in range(len(items)):
        index = (index + step) % len(items)
        if not items[index].disabled:
            return index
    return current


def _navigation_target(
    items: Sequence[CommandItem],
    current: int | None,
    key_code: int | None,
) -> int | None:
    if key_code == _VK_HOME:
        return _first_enabled(items)
    if key_code == _VK_END:
        return _last_enabled(items)
    if key_code not in {_VK_UP, _VK_DOWN}:
        return None
    return _next_enabled(items, current, -1 if key_code == _VK_UP else 1)


def _normalize_index(index: int, count: int, label: str) -> int:
    normalized = int(index)
    if not 0 <= normalized < count:
        raise IndexError(f"{label} is out of range.")
    return normalized


def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
    platform_event = event.data.get("event")
    if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
        return platform_event
    return None


def _positive(value: float, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return normalized


__all__ = ["CommandPalette", "ContextMenu"]
