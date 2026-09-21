"""Retained PropertyGrid and Inspector widgets for professional SwirUI applications."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TypeAlias

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

PropertyValue: TypeAlias = str | int | float | bool | None

_VK_BACK = 0x08
_VK_ESCAPE = 0x1B
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_DELETE = 0x2E

_BACKGROUND = Color.from_hex("#06101A")
_ROW_BACKGROUND = Color.from_hex("#081723")
_SELECTED_BACKGROUND = Color.from_hex("#0B3550")
_READ_ONLY_BACKGROUND = Color.from_hex("#07131D")
_EDITOR_BACKGROUND = Color.from_hex("#04111B")
_FOREGROUND = Color.from_hex("#DDF5FF")
_MUTED = Color.from_hex("#8DA8B8")
_ACCENT = Color.from_hex("#23C9FF")
_DIVIDER = Color.from_hex("#164D6B")


class PropertyEditorKind(StrEnum):
    """Editor contract used by retained PropertyGrid rows."""

    AUTO = "auto"
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


@dataclass(frozen=True, slots=True)
class PropertyItem:
    """Immutable property descriptor with stable identity and editor metadata."""

    key: Hashable
    label: str
    value: PropertyValue
    category: str = "General"
    description: str | None = None
    read_only: bool = False
    editor: PropertyEditorKind = PropertyEditorKind.AUTO

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("PropertyItem key must be hashable.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("PropertyItem label must be a non-empty string.")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("PropertyItem category must be a non-empty string.")
        if self.description is not None and not isinstance(self.description, str):
            raise TypeError("PropertyItem description must be a string or None.")
        if not isinstance(self.editor, PropertyEditorKind):
            raise TypeError("PropertyItem editor must be PropertyEditorKind.")
        _validate_value_for_kind(self.value, _resolved_kind(self))


class PropertyGrid(Widget):
    """Retained two-column property editor with keyboard and accessibility support."""

    def __init__(
        self,
        items: Sequence[PropertyItem],
        *,
        bounds: Rect,
        key: str | None = None,
        row_height: float = 44.0,
        label_fraction: float = 0.42,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Property grid",
        accessible_description: str | None = None,
    ) -> None:
        self._items = _validate_items(items)
        self._row_height = _positive(row_height, "row_height")
        self._label_fraction = float(label_fraction)
        if not math.isfinite(self._label_fraction) or not 0.2 <= self._label_fraction <= 0.8:
            raise ValueError("label_fraction must be finite and between 0.2 and 0.8.")
        self._selected_index = 0 if self._items else None
        self._editing_index: int | None = None
        self._edit_buffer = ""
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.TABLE,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self.on("text_input", self._on_text_input)
        self._sync_accessibility()

    @property
    def items(self) -> tuple[PropertyItem, ...]:
        return self._items

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_item(self) -> PropertyItem | None:
        if self._selected_index is None:
            return None
        return self._items[self._selected_index]

    @property
    def editing_index(self) -> int | None:
        return self._editing_index

    @property
    def editing_item(self) -> PropertyItem | None:
        if self._editing_index is None:
            return None
        return self._items[self._editing_index]

    @property
    def edit_buffer(self) -> str:
        return self._edit_buffer

    def set_items(self, items: Sequence[PropertyItem]) -> PropertyGrid:
        normalized = _validate_items(items)
        if normalized == self._items:
            return self
        selected_key = None if self.selected_item is None else self.selected_item.key
        editing_key = None if self.editing_item is None else self.editing_item.key
        self._items = normalized
        self._selected_index = _index_for_key(normalized, selected_key)
        if self._selected_index is None and normalized:
            self._selected_index = 0
        self._editing_index = _index_for_key(normalized, editing_key)
        if self._editing_index is not None and normalized[self._editing_index].read_only:
            self._editing_index = None
        if self._editing_index is None:
            self._edit_buffer = ""
        else:
            self._edit_buffer = _format_value(normalized[self._editing_index].value)
        self._sync_accessibility()
        self.invalidate(reason="items")
        return self

    def select_key(self, key: Hashable) -> PropertyGrid:
        index = _index_for_key(self._items, key)
        if index is None:
            raise KeyError(f"Unknown property key: {key!r}")
        return self._select_index(index)

    def set_value(self, key: Hashable, value: PropertyValue) -> PropertyGrid:
        index = _index_for_key(self._items, key)
        if index is None:
            raise KeyError(f"Unknown property key: {key!r}")
        item = self._items[index]
        if item.read_only:
            raise PermissionError(f"Property is read-only: {key!r}")
        kind = _resolved_kind(item)
        normalized = _coerce_value(value, kind)
        if normalized == item.value:
            return self
        updated = replace(item, value=normalized)
        mutable = list(self._items)
        mutable[index] = updated
        self._items = tuple(mutable)
        if self._editing_index == index:
            self._edit_buffer = _format_value(normalized)
        self._sync_accessibility()
        self.invalidate(reason="value")
        self.emit(
            "property_changed",
            index=index,
            key=item.key,
            item=updated,
            old_value=item.value,
            value=normalized,
        )
        return self

    def begin_edit(self, key: Hashable | None = None) -> PropertyGrid:
        if key is not None:
            self.select_key(key)
        item = self.selected_item
        if item is None or item.read_only:
            return self
        if _resolved_kind(item) is PropertyEditorKind.BOOLEAN:
            return self.toggle_selected()
        assert self._selected_index is not None
        self._editing_index = self._selected_index
        self._edit_buffer = _format_value(item.value)
        self._sync_accessibility()
        self.invalidate(reason="edit")
        self.emit("edit_started", index=self._editing_index, key=item.key, item=item)
        return self

    def set_edit_buffer(self, text: str) -> PropertyGrid:
        if self._editing_index is None:
            raise RuntimeError("No property is being edited.")
        if not isinstance(text, str):
            raise TypeError("Property edit buffer must be a string.")
        if text == self._edit_buffer:
            return self
        self._edit_buffer = text
        self.invalidate(reason="edit-buffer")
        return self

    def commit_edit(self) -> PropertyGrid:
        item = self.editing_item
        index = self._editing_index
        if item is None or index is None:
            return self
        value = _parse_buffer(self._edit_buffer, _resolved_kind(item))
        self._editing_index = None
        self._edit_buffer = ""
        self.set_value(item.key, value)
        self._sync_accessibility()
        self.invalidate(reason="edit-commit")
        self.emit("edit_committed", index=index, key=item.key, value=value)
        return self

    def cancel_edit(self) -> PropertyGrid:
        item = self.editing_item
        index = self._editing_index
        if item is None or index is None:
            return self
        self._editing_index = None
        self._edit_buffer = ""
        self._sync_accessibility()
        self.invalidate(reason="edit-cancel")
        self.emit("edit_cancelled", index=index, key=item.key)
        return self

    def toggle_selected(self) -> PropertyGrid:
        item = self.selected_item
        if item is None or item.read_only or _resolved_kind(item) is not PropertyEditorKind.BOOLEAN:
            return self
        return self.set_value(item.key, not bool(item.value))

    def row_bounds(self, index: int) -> Rect:
        normalized = _normalize_index(index, len(self._items), "Property-grid row")
        y = self.bounds.y + normalized * self._row_height
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
            corner_radius=CornerRadius.uniform(8.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        label_width = self.bounds.width * self._label_fraction
        for index, item in enumerate(self._items):
            row = self.row_bounds(index)
            if row.height <= 0.0 or row.y >= self.bounds.bottom:
                break
            selected = index == self._selected_index
            editing = index == self._editing_index
            row_node = SceneNode(
                key=f"{self.key}:row:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row,
                fill=(
                    _SELECTED_BACKGROUND
                    if selected
                    else _READ_ONLY_BACKGROUND if item.read_only else _ROW_BACKGROUND
                ),
                z_index=1,
                hit_testable=False,
            )
            name_text = f"{item.category} / {item.label}"
            row_node.add(
                SceneNode(
                    key=f"{self.key}:row:{index}:name",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        row.x + 12.0,
                        row.y + 12.0,
                        max(0.0, label_width - 22.0),
                        20.0,
                    ),
                    fill=_MUTED if item.read_only else _FOREGROUND,
                    text=name_text,
                    font_size=13.0,
                    font_family="Segoe UI",
                    z_index=3,
                    hit_testable=False,
                )
            )
            value_x = row.x + label_width
            value_bounds = Rect(
                value_x + 1.0,
                row.y + 4.0,
                max(0.0, row.right - value_x - 5.0),
                max(0.0, row.height - 8.0),
            )
            if editing:
                row_node.add(
                    SceneNode(
                        key=f"{self.key}:row:{index}:editor",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=value_bounds,
                        fill=_EDITOR_BACKGROUND,
                        corner_radius=CornerRadius.uniform(5.0),
                        z_index=2,
                        hit_testable=False,
                    )
                )
            row_node.add(
                SceneNode(
                    key=f"{self.key}:row:{index}:value",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        value_x + 12.0,
                        row.y + 12.0,
                        max(0.0, row.right - value_x - 22.0),
                        20.0,
                    ),
                    fill=_MUTED if item.read_only else _FOREGROUND,
                    text=self._edit_buffer if editing else _format_value(item.value),
                    font_size=13.0,
                    font_family="Segoe UI",
                    z_index=3,
                    hit_testable=False,
                )
            )
            row_node.add(
                SceneNode(
                    key=f"{self.key}:row:{index}:divider",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(value_x, row.y + 5.0, 1.0, max(0.0, row.height - 10.0)),
                    fill=_DIVIDER,
                    z_index=3,
                    hit_testable=False,
                )
            )
            if selected:
                row_node.add(
                    SceneNode(
                        key=f"{self.key}:row:{index}:accent",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(row.x, row.y + 5.0, 3.0, max(0.0, row.height - 10.0)),
                        fill=_ACCENT,
                        z_index=4,
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
        rows = tuple(self._accessibility_row(index, item) for index, item in enumerate(self._items))
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.TABLE,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=rows,
            row_count=len(self._items),
            column_count=2,
        )

    def _accessibility_row(self, index: int, item: PropertyItem) -> AccessibilityNode:
        selected = index == self._selected_index
        value_text = (
            self._edit_buffer if index == self._editing_index else _format_value(item.value)
        )
        description = item.description
        if item.read_only:
            description = "Read only" if description is None else f"{description}. Read only"
        return AccessibilityNode(
            key=f"{self.key}:a11y:row:{index}",
            role=AccessibilityRole.ROW,
            name=item.label,
            description=description,
            enabled=self.enabled,
            focusable=False,
            focused=False,
            selected=selected,
            active=selected,
            row_index=index,
            children=(
                AccessibilityNode(
                    key=f"{self.key}:a11y:row:{index}:name",
                    role=AccessibilityRole.CELL,
                    name=item.label,
                    description=item.category,
                    enabled=self.enabled,
                    focusable=False,
                    focused=False,
                    row_index=index,
                    column_index=0,
                ),
                AccessibilityNode(
                    key=f"{self.key}:a11y:row:{index}:value",
                    role=AccessibilityRole.CELL,
                    name=f"{item.label} value",
                    description=description,
                    enabled=self.enabled and not item.read_only,
                    focusable=False,
                    focused=False,
                    value_text=value_text,
                    row_index=index,
                    column_index=1,
                ),
            ),
        )

    def _select_index(self, index: int) -> PropertyGrid:
        normalized = _normalize_index(index, len(self._items), "Property-grid row")
        if normalized == self._selected_index:
            return self
        if self._editing_index is not None:
            self.cancel_edit()
        self._selected_index = normalized
        self._sync_accessibility()
        self.invalidate(reason="selection")
        item = self._items[normalized]
        self.emit("selection_changed", index=normalized, key=item.key, item=item)
        return self

    def _sync_accessibility(self) -> None:
        item = self.selected_item
        if item is None:
            self.accessible_value_text = "No properties"
            return
        index = self._selected_index
        assert index is not None
        suffix = ", editing" if self._editing_index == index else ""
        self.accessible_value_text = (
            f"{item.label}, property {index + 1} of {len(self._items)}{suffix}"
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.POINTER_DOWN)
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
        index = int((platform_event.y - self.bounds.y) // self._row_height)
        if not 0 <= index < len(self._items):
            return
        self._select_index(index)
        item = self._items[index]
        value_start = self.bounds.x + self.bounds.width * self._label_fraction
        if platform_event.x >= value_start and not item.read_only:
            if _resolved_kind(item) is PropertyEditorKind.BOOLEAN:
                self.toggle_selected()
            else:
                self.begin_edit()
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        key_code = platform_event.key_code
        if self._editing_index is not None:
            if key_code == _VK_ESCAPE:
                self.cancel_edit()
                event.prevent_default()
                return
            if key_code == _VK_RETURN:
                try:
                    self.commit_edit()
                except ValueError as exc:
                    editing_item = self.editing_item
                    assert editing_item is not None
                    self.emit("edit_error", message=str(exc), key=editing_item.key)
                event.prevent_default()
                return
            if key_code == _VK_BACK and self._edit_buffer:
                self.set_edit_buffer(self._edit_buffer[:-1])
                event.prevent_default()
                return
            if key_code == _VK_DELETE:
                self.set_edit_buffer("")
                event.prevent_default()
                return
            return

        if key_code in {_VK_RETURN, _VK_SPACE}:
            item = self.selected_item
            if item is not None:
                if _resolved_kind(item) is PropertyEditorKind.BOOLEAN:
                    self.toggle_selected()
                elif key_code == _VK_RETURN:
                    self.begin_edit()
                else:
                    return
                event.prevent_default()
            return
        target = _navigation_target(len(self._items), self._selected_index, key_code)
        if target is None:
            return
        self._select_index(target)
        event.prevent_default()

    def _on_text_input(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.TEXT_INPUT)
        if not self.enabled or self._editing_index is None or platform_event is None:
            return
        text = platform_event.text
        if not text or any(character in "\r\n\t" for character in text):
            return
        self.set_edit_buffer(self._edit_buffer + text)
        event.prevent_default()


class Inspector(PropertyGrid):
    """PropertyGrid specialization with Inspector accessibility semantics."""

    def __init__(
        self,
        items: Sequence[PropertyItem],
        *,
        bounds: Rect,
        key: str | None = None,
        row_height: float = 44.0,
        label_fraction: float = 0.42,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Inspector",
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            items,
            bounds=bounds,
            key=key,
            row_height=row_height,
            label_fraction=label_fraction,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )


def _resolved_kind(item: PropertyItem) -> PropertyEditorKind:
    if item.editor is not PropertyEditorKind.AUTO:
        return item.editor
    value = item.value
    if isinstance(value, bool):
        return PropertyEditorKind.BOOLEAN
    if isinstance(value, int):
        return PropertyEditorKind.INTEGER
    if isinstance(value, float):
        return PropertyEditorKind.FLOAT
    return PropertyEditorKind.TEXT


def _validate_value_for_kind(value: PropertyValue, kind: PropertyEditorKind) -> None:
    if value is None and kind is PropertyEditorKind.TEXT:
        return
    if kind is PropertyEditorKind.BOOLEAN and not isinstance(value, bool):
        raise TypeError("Boolean property values must be bool.")
    if kind is PropertyEditorKind.INTEGER and (
        not isinstance(value, int) or isinstance(value, bool)
    ):
        raise TypeError("Integer property values must be int.")
    if kind is PropertyEditorKind.FLOAT and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        raise TypeError("Float property values must be numeric.")
    if kind is PropertyEditorKind.TEXT and value is not None and not isinstance(value, str):
        raise TypeError("Text property values must be str or None.")


def _coerce_value(value: PropertyValue, kind: PropertyEditorKind) -> PropertyValue:
    if kind is PropertyEditorKind.TEXT:
        if value is None or isinstance(value, str):
            return value
        raise TypeError("Text property values must be str or None.")
    if kind is PropertyEditorKind.BOOLEAN:
        if isinstance(value, bool):
            return value
        raise TypeError("Boolean property values must be bool.")
    if kind is PropertyEditorKind.INTEGER:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise TypeError("Integer property values must be int.")
    if kind is PropertyEditorKind.FLOAT:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        raise TypeError("Float property values must be numeric.")
    raise AssertionError(f"Unsupported PropertyEditorKind: {kind}")


def _parse_buffer(text: str, kind: PropertyEditorKind) -> PropertyValue:
    if kind is PropertyEditorKind.TEXT:
        return text
    if kind is PropertyEditorKind.INTEGER:
        try:
            return int(text.strip())
        except ValueError as exc:
            raise ValueError("Property value must be a valid integer.") from exc
    if kind is PropertyEditorKind.FLOAT:
        try:
            value = float(text.strip())
        except ValueError as exc:
            raise ValueError("Property value must be a valid number.") from exc
        if not math.isfinite(value):
            raise ValueError("Property value must be finite.")
        return value
    raise ValueError("Boolean properties are toggled directly and do not use text editing.")


def _format_value(value: PropertyValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def _validate_items(items: Sequence[PropertyItem]) -> tuple[PropertyItem, ...]:
    normalized = tuple(items)
    keys: set[Hashable] = set()
    for item in normalized:
        if not isinstance(item, PropertyItem):
            raise TypeError("PropertyGrid requires PropertyItem values.")
        if item.key in keys:
            raise ValueError(f"Duplicate property key: {item.key!r}")
        keys.add(item.key)
    return normalized


def _index_for_key(
    items: Sequence[PropertyItem],
    key: Hashable | None,
) -> int | None:
    if key is None:
        return None
    return next((index for index, item in enumerate(items) if item.key == key), None)


def _normalize_index(index: int, count: int, label: str) -> int:
    normalized = int(index)
    if not 0 <= normalized < count:
        raise IndexError(f"{label} is out of range.")
    return normalized


def _navigation_target(
    count: int,
    current: int | None,
    key_code: int | None,
) -> int | None:
    if count <= 0:
        return None
    if key_code == _VK_HOME:
        return 0
    if key_code == _VK_END:
        return count - 1
    if key_code in {_VK_UP, _VK_LEFT}:
        return max(0, 0 if current is None else current - 1)
    if key_code in {_VK_DOWN, _VK_RIGHT}:
        return min(count - 1, 0 if current is None else current + 1)
    return None


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


__all__ = ["Inspector", "PropertyEditorKind", "PropertyGrid", "PropertyItem"]
