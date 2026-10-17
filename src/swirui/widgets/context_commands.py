"""Retained context-menu and command-palette widgets for SwirUI applications."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.theme import Theme

from .base import Widget
from .command_surfaces import CommandItem
from .command_viewport import CommandViewport
from .input import Input

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
        theme: Theme | None = None,
        row_height: float = 38.0,
        dismiss_on_invoke: bool = True,
        opacity: float = 1.0,
        z_index: int = 100,
        accessible_name: str = "Context menu",
        accessible_description: str | None = None,
    ) -> None:
        self._row_viewport = CommandViewport()
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
        self._background = _BACKGROUND
        self._item_background = _ROW_BACKGROUND
        self._active_item_background = _ACTIVE_BACKGROUND
        self._input_background = _INPUT_BACKGROUND
        self._foreground = _FOREGROUND
        self._muted = _MUTED
        self._accent = _ACCENT
        self._scroll_track = _ROW_BACKGROUND
        self._scroll_thumb = _ACCENT
        self._font_family = "Segoe UI"
        self._corner_radius = 10.0 if isinstance(self, ContextMenu) else 12.0
        self._bind_theme(
            theme,
            {
                "_background": ("surface", "surface", _BACKGROUND),
                "_item_background": ("surface", "surface", _ROW_BACKGROUND),
                "_active_item_background": ("surface", "selection", _ACTIVE_BACKGROUND),
                "_input_background": ("surface", "raised", _INPUT_BACKGROUND),
                "_foreground": ("text", "text", _FOREGROUND),
                "_muted": ("text", "muted", _MUTED),
                "_accent": ("surface", "accent", _ACCENT),
                "_scroll_track": ("surface", "border", _ROW_BACKGROUND),
                "_scroll_thumb": ("surface", "accent", _ACCENT),
                "_font_family": ("token", "font_family", "Segoe UI"),
                "_corner_radius": ("token", "control_radius", self._corner_radius),
            },
        )
        self._enable_theme_focus_frame()
        self.on("pointer_scroll", self._on_pointer_scroll)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
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

    def _viewport(self) -> CommandViewport:
        self._row_viewport.configure(self.bounds, self._row_height, len(self._items))
        return self._row_viewport

    @property
    def scroll_offset(self) -> float:
        return self._viewport().offset

    def scroll_by(self, delta: float) -> ContextMenu:
        if self._viewport().scroll_by(float(delta)):
            self.invalidate(reason="scroll_offset")
        return self

    def _visible_indices(self) -> range:
        return self._viewport().visible_indices()

    def row_bounds(self, index: int) -> Rect:
        index = _normalize_index(index, len(self._items), "Command row")
        return self._viewport().row_bounds(index)

    def _on_pointer_scroll(self, event: Event) -> None:
        self._viewport().on_scroll(self, event)

    def _on_pointer_move(self, event: Event) -> None:
        self._viewport().on_pointer_move(self, event)

    def _on_pointer_up(self, event: Event) -> None:
        self._viewport().on_pointer_up(self, event)

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
        if not self.visible:
            root.opacity = 0.0
            root.hit_testable = False
            return root
        rows = SceneNode(
            key=f"{self.key}:rows",
            kind=SceneNodeKind.GROUP,
            bounds=self._viewport().bounds,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(rows)
        for index in self._visible_indices():
            item = self._items[index]
            row = self.row_bounds(index)
            if row.height <= 0.0 or row.y >= self.bounds.bottom:
                break
            active = index == self._active_index
            node = SceneNode(
                key=f"{self.key}:item:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row,
                fill=self._active_item_background if active else self._item_background,
                z_index=1,
                hit_testable=False,
            )
            _add_command_text(
                node,
                self.key,
                "item",
                index,
                row,
                item,
                self._foreground,
                self._muted,
                self._font_family,
                self.enabled,
            )
            if active:
                _add_active_accent(node, self.key, "item", index, row, self._accent)
            rows.add(node)
        self._viewport().add_scrollbar(root, self.key, self._scroll_track, self._scroll_thumb)
        self._add_theme_focus_frame(root)
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
        self._viewport().reveal(self._active_index)
        active = self.active_item
        if active is None:
            self.accessible_value_text = f"No active command of {len(self._items)}"
            return
        index = self._active_index
        assert index is not None
        self.accessible_value_text = f"{active.label}, command {index + 1} of {len(self._items)}"

    def _on_pointer_down(self, event: Event) -> None:
        if self._viewport().on_pointer_down(self, event):
            return
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
        viewport = self._viewport()
        index = int((platform_event.y - viewport.bounds.y + viewport.offset) // self._row_height)
        if index in self._visible_indices():
            self._activate_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        if event.source is not self or event.default_prevented:
            return
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


class CommandPalette(Input):
    """Searchable retained command palette with native text-input and keyboard routing."""

    def __init__(
        self,
        items: Sequence[CommandItem],
        *,
        bounds: Rect,
        key: str | None = None,
        theme: Theme | None = None,
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
        self._row_viewport = CommandViewport()
        self._items = _validate_items(items)
        self._header_height = _positive(header_height, "header_height")
        self._row_height = _positive(row_height, "row_height")
        self._max_visible_rows = int(max_visible_rows)
        if self._max_visible_rows <= 0:
            raise ValueError("max_visible_rows must be positive.")
        self._dismiss_on_invoke = bool(dismiss_on_invoke)
        query = self._normalize_value(_normalize_query(query))
        self._filtered = _filter_items(self._items, query)
        self._active_index = _first_enabled(self._filtered)
        super().__init__(
            query,
            bounds=bounds,
            placeholder="Type a command...",
            font_size=15,
            padding=14,
            key=key,
            opacity=opacity,
            z_index=z_index,
            accessibility_role=AccessibilityRole.DIALOG,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._background = _BACKGROUND
        self._item_background = _ROW_BACKGROUND
        self._active_item_background = _ACTIVE_BACKGROUND
        self._input_background = _INPUT_BACKGROUND
        self._foreground = _FOREGROUND
        self._muted = _MUTED
        self._accent = _ACCENT
        self._scroll_track = _ROW_BACKGROUND
        self._scroll_thumb = _ACCENT
        self._font_family = "Segoe UI"
        self._corner_radius = 10.0 if isinstance(self, ContextMenu) else 12.0
        self._bind_theme(
            theme,
            {
                "_background": ("surface", "surface", _BACKGROUND),
                "_item_background": ("surface", "surface", _ROW_BACKGROUND),
                "_active_item_background": ("surface", "selection", _ACTIVE_BACKGROUND),
                "_input_background": ("surface", "raised", _INPUT_BACKGROUND),
                "_foreground": ("text", "text", _FOREGROUND),
                "_muted": ("text", "muted", _MUTED),
                "_accent": ("surface", "accent", _ACCENT),
                "_scroll_track": ("surface", "border", _ROW_BACKGROUND),
                "_scroll_thumb": ("surface", "accent", _ACCENT),
                "_font_family": ("token", "font_family", "Segoe UI"),
                "_corner_radius": ("token", "control_radius", self._corner_radius),
                "_placeholder_color": ("text", "muted", _MUTED),
                "_selection_color": ("surface", "selection", _ACTIVE_BACKGROUND),
                "_caret_color": ("surface", "focus", _ACCENT),
            },
        )
        self._enable_theme_focus_frame()
        self.on("pointer_scroll", self._on_pointer_scroll)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
        self.on("changed", self._on_query_changed)
        self._sync_accessibility()

    @property
    def items(self) -> tuple[CommandItem, ...]:
        return self._items

    @property
    def query(self) -> str:
        return self.value

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
        normalized = self._normalize_value(_normalize_query(query))
        if normalized != self.value:
            self.value = normalized
            self.select(len(self.value), len(self.value))
        return self

    def _on_query_changed(self, _event: Event) -> None:
        active_key = None if self.active_item is None else self.active_item.key
        self._apply_filter(active_key=active_key, reason="query")
        self.emit("query_changed", query=self.value, result_count=len(self._filtered))

    def intrinsic_size(self, available: Size | None = None) -> Size:
        return Widget.intrinsic_size(self, available)

    def _content_bounds(self) -> Rect:
        return Rect(
            self.bounds.x + 14,
            self.bounds.y + 13,
            max(0, self.bounds.width - 28),
            max(0, min(self._header_height, self.bounds.height) - 26),
        )

    def _normalize_value(self, value: str) -> str:
        return self._normalize_inserted_text(value, allow_tabs=True)

    def _normalize_inserted_text(self, text: str, *, allow_tabs: bool = False) -> str:
        text = text.replace("\u2028", " ").replace("\u2029", " ")
        if allow_tabs:
            text = (
                text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ").replace("\t", " ")
            )
        return "".join(char for char in text if ord(char) >= 32 and not 0x7F <= ord(char) <= 0x9F)

    def clear_query(self) -> CommandPalette:
        return self.set_query("")

    def activate_key(self, key: Hashable) -> CommandPalette:
        index = _index_for_key(self._filtered, key)
        if index is None:
            raise KeyError(f"Unknown visible command key: {key!r}")
        return self._activate_index(index)

    def _viewport(self) -> CommandViewport:
        self._row_viewport.configure(
            Rect(
                self.bounds.x,
                self.bounds.y + min(self._header_height, self.bounds.height),
                self.bounds.width,
                min(
                    self._max_visible_rows * self._row_height,
                    max(0.0, self.bounds.height - self._header_height),
                ),
            ),
            self._row_height,
            len(self._filtered),
        )
        return self._row_viewport

    @property
    def scroll_offset(self) -> float:
        return self._viewport().offset

    def scroll_by(self, delta: float) -> CommandPalette:
        if self._viewport().scroll_by(float(delta)):
            self.invalidate(reason="scroll_offset")
        return self

    def _visible_indices(self) -> range:
        return self._viewport().visible_indices()

    def row_bounds(self, index: int) -> Rect:
        index = _normalize_index(index, len(self._filtered), "Command row")
        return self._viewport().row_bounds(index)

    def _on_pointer_scroll(self, event: Event) -> None:
        self._viewport().on_scroll(self, event)

    def _on_pointer_move(self, event: Event) -> None:
        self._viewport().on_pointer_move(self, event)

    def _on_pointer_up(self, event: Event) -> None:
        self._viewport().on_pointer_up(self, event)

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
            fill=self._input_background,
            z_index=1,
            hit_testable=False,
        )
        self._build_single_line_content(header_node, self._content_bounds())
        root.add(header_node)

        if not self._filtered:
            root.add(
                SceneNode(
                    key=f"{self.key}:empty",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(header.x + 14, header.bottom + 12, max(0, header.width - 28), 24),
                    fill=self._muted,
                    text="No matching commands",
                    font_size=14,
                    font_family=self._font_family,
                    z_index=2,
                    hit_testable=False,
                )
            )

        rows = SceneNode(
            key=f"{self.key}:rows",
            kind=SceneNodeKind.GROUP,
            bounds=self._viewport().bounds,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(rows)
        for index in self._visible_indices():
            item = self._filtered[index]
            row = self.row_bounds(index)
            if row.height <= 0.0 or row.y >= self.bounds.bottom:
                break
            active = index == self._active_index
            node = SceneNode(
                key=f"{self.key}:result:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row,
                fill=self._active_item_background if active else self._item_background,
                z_index=1,
                hit_testable=False,
            )
            _add_command_text(
                node,
                self.key,
                "result",
                index,
                row,
                item,
                self._foreground,
                self._muted,
                self._font_family,
                self.enabled,
            )
            if active:
                _add_active_accent(node, self.key, "result", index, row, self._accent)
            rows.add(node)
        self._viewport().add_scrollbar(root, self.key, self._scroll_track, self._scroll_thumb)
        self._add_theme_focus_frame(root)
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
            for index in self._visible_indices()
            for item in (self._filtered[index],)
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
        self._filtered = _filter_items(self._items, self.value)
        self._active_index = _index_for_key(self._filtered, active_key)
        if self._active_index is None or self._filtered[self._active_index].disabled:
            self._active_index = _first_enabled(self._filtered)
        self._sync_accessibility()
        self.invalidate(reason=reason)

    def _sync_accessibility(self) -> None:
        self._viewport().reveal(self._active_index)
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
        if self._viewport().on_pointer_down(self, event):
            return
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
        if platform_event.y < self.bounds.y + self._header_height:
            super()._on_pointer_down(event)
            return
        viewport = self._viewport()
        if platform_event.y >= viewport.bounds.bottom:
            return
        visible = self._visible_indices()
        index = int((platform_event.y - viewport.bounds.y + viewport.offset) // self._row_height)
        if index in visible:
            self._activate_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        if event.source is not self or event.default_prevented:
            return
        native = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or not self.visible or native is None:
            return
        code = native.key_code
        if native.alt or native.meta:
            return
        # Preserve result Home/End; Ctrl or Shift targets the query boundary.
        if code in (_VK_HOME, _VK_END) and (native.ctrl or native.shift):
            self._move_caret(0 if code == _VK_HOME else len(self.value), extend=native.shift)
            event.prevent_default()
            return
        if native.ctrl:
            super()._on_key_down(event)
            return
        if code == _VK_ESCAPE:
            self.visible = False
            self.emit("dismissed")
            event.prevent_default()
            return
        if code == _VK_RETURN:
            if self._active_index is not None:
                self._activate_index(self._active_index)
            event.prevent_default()
            return
        target = _navigation_target(self._filtered, self._active_index, code)
        if target is not None:
            self._active_index = target
            self._sync_accessibility()
            self.invalidate(reason="selection")
            event.prevent_default()
            return
        super()._on_key_down(event)

    def _on_text_input(self, event: Event) -> None:
        if event.source is not self or event.default_prevented or not self.visible:
            return
        super()._on_text_input(event)


def _add_command_text(
    node: SceneNode,
    root_key: str,
    kind: str,
    index: int,
    row: Rect,
    item: CommandItem,
    foreground: Color,
    muted: Color,
    font_family: str,
    enabled: bool,
) -> None:
    shortcut_width = min(102.0, max(0.0, row.width - 28.0)) if item.shortcut else 0.0
    label_width = max(0.0, row.width - 28.0 - shortcut_width - (12.0 if item.shortcut else 0.0))
    node.add(
        SceneNode(
            key=f"{root_key}:{kind}:{index}:label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(row.x + 14.0, row.y + 9.0, label_width, 20.0),
            fill=muted if item.disabled or not enabled else foreground,
            text=item.label,
            font_size=14.0,
            font_family=font_family,
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
                fill=muted,
                text=item.shortcut,
                font_size=11.0,
                font_family=font_family,
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
    accent: Color,
) -> None:
    node.add(
        SceneNode(
            key=f"{root_key}:{kind}:{index}:accent",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(row.x, row.y + 5.0, 3.0, max(0.0, row.height - 10.0)),
            fill=accent,
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
    return query


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
        (index for index in range(len(items) - 1, -1, -1) if not items[index].disabled),
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
