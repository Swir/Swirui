"""Professional retained command surfaces for SwirUI applications."""

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
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_RETURN = 0x0D
_VK_SPACE = 0x20

_DEFAULT_BACKGROUND = Color.from_hex("#06101A")
_DEFAULT_ITEM_BACKGROUND = Color.from_hex("#081723")
_DEFAULT_ACTIVE_ITEM_BACKGROUND = Color.from_hex("#0B3550")
_DEFAULT_FOREGROUND = Color.from_hex("#DDF5FF")
_DEFAULT_MUTED = Color.from_hex("#8DA8B8")
_DEFAULT_ACCENT = Color.from_hex("#23C9FF")


@dataclass(frozen=True, slots=True)
class CommandItem:
    """Immutable command descriptor with stable application identity."""

    key: Hashable
    label: str
    shortcut: str | None = None
    disabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("CommandItem.key must be hashable.")
        label = self.label.strip()
        if not label:
            raise ValueError("CommandItem.label must not be empty.")
        object.__setattr__(self, "label", label)
        if self.shortcut is not None:
            shortcut = self.shortcut.strip()
            if not shortcut:
                raise ValueError("CommandItem.shortcut must not be empty when provided.")
            object.__setattr__(self, "shortcut", shortcut)


@dataclass(frozen=True, slots=True)
class RibbonGroup:
    """One ribbon tab and its retained command collection."""

    key: Hashable
    label: str
    items: tuple[CommandItem, ...]

    def __init__(
        self,
        key: Hashable,
        label: str,
        items: Sequence[CommandItem],
    ) -> None:
        if not isinstance(key, Hashable):
            raise TypeError("RibbonGroup.key must be hashable.")
        normalized_label = label.strip()
        if not normalized_label:
            raise ValueError("RibbonGroup.label must not be empty.")
        normalized_items = _validate_items(items)
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", normalized_label)
        object.__setattr__(self, "items", normalized_items)


class _CommandStrip(Widget):
    def __init__(
        self,
        items: Sequence[CommandItem],
        *,
        bounds: Rect,
        key: str | None,
        item_width: float,
        role: AccessibilityRole,
        item_role: AccessibilityRole,
        accessible_name: str,
        accessible_description: str | None,
        opacity: float,
        z_index: int,
    ) -> None:
        self._items = _validate_items(items)
        self._item_width = _positive(item_width, "item_width")
        self._item_role = item_role
        self._active_index = _first_enabled(self._items)
        self._background = _DEFAULT_BACKGROUND
        self._item_background = _DEFAULT_ITEM_BACKGROUND
        self._active_item_background = _DEFAULT_ACTIVE_ITEM_BACKGROUND
        self._foreground = _DEFAULT_FOREGROUND
        self._muted = _DEFAULT_MUTED
        self._accent = _DEFAULT_ACCENT
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=role,
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

    def set_items(self, items: Sequence[CommandItem]) -> _CommandStrip:
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

    def activate_index(self, index: int) -> _CommandStrip:
        normalized = self._normalize_index(index)
        item = self._items[normalized]
        if item.disabled:
            return self
        changed = normalized != self._active_index
        self._active_index = normalized
        self._sync_accessibility()
        if changed:
            self.invalidate(reason="selection")
        self.emit("command_invoked", index=normalized, key=item.key, item=item)
        return self

    def activate_key(self, key: Hashable) -> _CommandStrip:
        index = _index_for_key(self._items, key)
        if index is None:
            raise KeyError(f"Unknown command key: {key!r}")
        return self.activate_index(index)

    def item_bounds(self, index: int) -> Rect:
        normalized = self._normalize_index(index)
        return Rect(
            self.bounds.x + self._item_width * normalized,
            self.bounds.y,
            self._item_width,
            self.bounds.height,
        )

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            corner_radius=CornerRadius.uniform(8.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        for index, item in enumerate(self._items):
            cell = self.item_bounds(index)
            if cell.x >= self.bounds.right:
                break
            active = index == self._active_index
            node = SceneNode(
                key=f"{self.key}:item:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=cell,
                fill=self._active_item_background if active else self._item_background,
                z_index=1,
                hit_testable=False,
            )
            if active:
                node.add(
                    SceneNode(
                        key=f"{self.key}:item:{index}:accent",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            cell.x + 8.0,
                            cell.bottom - 3.0,
                            max(0.0, cell.width - 16.0),
                            3.0,
                        ),
                        fill=self._accent,
                        z_index=2,
                        hit_testable=False,
                    )
                )
            node.add(
                SceneNode(
                    key=f"{self.key}:item:{index}:label",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        cell.x + 10.0,
                        cell.y + 8.0,
                        max(0.0, cell.width - 20.0),
                        20.0,
                    ),
                    fill=self._muted if item.disabled else self._foreground,
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
                        key=f"{self.key}:item:{index}:shortcut",
                        kind=SceneNodeKind.TEXT,
                        bounds=Rect(
                            cell.x + 10.0,
                            cell.bottom - 22.0,
                            max(0.0, cell.width - 20.0),
                            16.0,
                        ),
                        fill=self._muted,
                        text=item.shortcut,
                        font_size=11.0,
                        font_family="Segoe UI",
                        z_index=3,
                        hit_testable=False,
                    )
                )
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
                role=self._item_role,
                name=item.label,
                description=item.shortcut,
                enabled=self.enabled and not item.disabled,
                focusable=False,
                focused=False,
                active=index == self._active_index,
                selected=index == self._active_index,
            )
            for index, item in enumerate(self._items)
        )
        return AccessibilityNode(
            key=self.key,
            role=self.accessibility_role,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=children,
        )

    def _sync_accessibility(self) -> None:
        active = self.active_item
        if active is None:
            self.accessible_value_text = f"No active command of {len(self._items)}"
        else:
            index = self._active_index
            assert index is not None
            self.accessible_value_text = (
                f"{active.label}, command {index + 1} of {len(self._items)}"
            )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
            or not self._items
            or not (
                self.bounds.x <= platform_event.x < self.bounds.right
                and self.bounds.y <= platform_event.y < self.bounds.bottom
            )
        ):
            return
        index = int((platform_event.x - self.bounds.x) // self._item_width)
        if 0 <= index < len(self._items):
            self.activate_index(index)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._items:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        key_code = platform_event.key_code
        if key_code in {_VK_RETURN, _VK_SPACE}:
            if self._active_index is not None:
                self.activate_index(self._active_index)
                event.prevent_default()
            return
        target = self._navigation_target(key_code)
        if target is None:
            return
        self._active_index = target
        self._sync_accessibility()
        self.invalidate(reason="selection")
        event.prevent_default()

    def _navigation_target(self, key_code: int | None) -> int | None:
        if key_code == _VK_HOME:
            return _first_enabled(self._items)
        if key_code == _VK_END:
            return _last_enabled(self._items)
        if key_code not in {_VK_LEFT, _VK_RIGHT}:
            return None
        return _next_enabled(
            self._items,
            self._active_index,
            -1 if key_code == _VK_LEFT else 1,
        )

    def _normalize_index(self, index: int) -> int:
        normalized = int(index)
        if not 0 <= normalized < len(self._items):
            raise IndexError("Command index is out of range.")
        return normalized


class Toolbar(_CommandStrip):
    """Horizontal command toolbar with retained keyboard/pointer interaction."""

    def __init__(
        self,
        items: Sequence[CommandItem],
        *,
        bounds: Rect,
        key: str | None = None,
        item_width: float = 104.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Toolbar",
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            items,
            bounds=bounds,
            key=key,
            item_width=item_width,
            role=AccessibilityRole.GROUP,
            item_role=AccessibilityRole.BUTTON,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            opacity=opacity,
            z_index=z_index,
        )


class MenuBar(_CommandStrip):
    """Application menu bar exposing MENU / MENU_ITEM accessibility semantics."""

    def __init__(
        self,
        items: Sequence[CommandItem],
        *,
        bounds: Rect,
        key: str | None = None,
        item_width: float = 92.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Menu bar",
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            items,
            bounds=bounds,
            key=key,
            item_width=item_width,
            role=AccessibilityRole.MENU,
            item_role=AccessibilityRole.MENU_ITEM,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            opacity=opacity,
            z_index=z_index,
        )


class Ribbon(Widget):
    """Retained tabbed ribbon with stable group identity and command activation."""

    def __init__(
        self,
        groups: Sequence[RibbonGroup],
        *,
        bounds: Rect,
        key: str | None = None,
        selected_key: Hashable | None = None,
        tab_width: float = 112.0,
        tab_height: float = 34.0,
        command_width: float = 108.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Ribbon",
        accessible_description: str | None = None,
    ) -> None:
        self._groups = _validate_groups(groups)
        self._tab_width = _positive(tab_width, "tab_width")
        self._tab_height = _positive(tab_height, "tab_height")
        self._command_width = _positive(command_width, "command_width")
        self._selected_index = self._initial_group_index(selected_key)
        self._active_command_index = self._first_active_command()
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
        self._sync_accessibility()

    @property
    def groups(self) -> tuple[RibbonGroup, ...]:
        return self._groups

    @property
    def selected_group(self) -> RibbonGroup | None:
        if self._selected_index is None:
            return None
        return self._groups[self._selected_index]

    @property
    def selected_key(self) -> Hashable | None:
        group = self.selected_group
        return None if group is None else group.key

    @property
    def active_command(self) -> CommandItem | None:
        group = self.selected_group
        if group is None or self._active_command_index is None:
            return None
        return group.items[self._active_command_index]

    def select_group(self, key: Hashable) -> Ribbon:
        index = _index_for_group_key(self._groups, key)
        if index is None:
            raise KeyError(f"Unknown ribbon group key: {key!r}")
        if index == self._selected_index:
            return self
        previous = self.selected_group
        self._selected_index = index
        self._active_command_index = self._first_active_command()
        self._sync_accessibility()
        self.invalidate(reason="selection")
        self.emit(
            "group_changed",
            index=index,
            key=self._groups[index].key,
            group=self._groups[index],
            previous=previous,
        )
        return self

    def activate_command(self, key: Hashable) -> Ribbon:
        group = self.selected_group
        if group is None:
            raise KeyError(f"Unknown ribbon command key: {key!r}")
        index = _index_for_key(group.items, key)
        if index is None:
            raise KeyError(f"Unknown ribbon command key: {key!r}")
        item = group.items[index]
        if item.disabled:
            return self
        self._active_command_index = index
        self._sync_accessibility()
        self.invalidate(reason="selection")
        self.emit("command_invoked", index=index, key=item.key, item=item, group=group)
        return self

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_DEFAULT_BACKGROUND,
            corner_radius=CornerRadius.uniform(8.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        for index, group in enumerate(self._groups):
            tab = Rect(
                self.bounds.x + index * self._tab_width,
                self.bounds.y,
                self._tab_width,
                min(self._tab_height, self.bounds.height),
            )
            active = index == self._selected_index
            tab_node = SceneNode(
                key=f"{self.key}:group:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=tab,
                fill=_DEFAULT_ACTIVE_ITEM_BACKGROUND if active else _DEFAULT_ITEM_BACKGROUND,
                z_index=1,
                hit_testable=False,
            )
            tab_node.add(
                SceneNode(
                    key=f"{self.key}:group:{index}:label",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        tab.x + 10.0,
                        tab.y + 7.0,
                        max(0.0, tab.width - 20.0),
                        18.0,
                    ),
                    fill=_DEFAULT_FOREGROUND,
                    text=group.label,
                    font_size=13.0,
                    font_family="Segoe UI",
                    z_index=2,
                    hit_testable=False,
                )
            )
            root.add(tab_node)

        group = self.selected_group
        if group is None:
            return root
        command_y = self.bounds.y + self._tab_height
        command_height = max(0.0, self.bounds.bottom - command_y)
        for index, item in enumerate(group.items):
            cell = Rect(
                self.bounds.x + index * self._command_width,
                command_y,
                self._command_width,
                command_height,
            )
            if cell.x >= self.bounds.right:
                break
            active = index == self._active_command_index
            node = SceneNode(
                key=f"{self.key}:command:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=cell,
                fill=_DEFAULT_ACTIVE_ITEM_BACKGROUND if active else _DEFAULT_ITEM_BACKGROUND,
                z_index=1,
                hit_testable=False,
            )
            node.add(
                SceneNode(
                    key=f"{self.key}:command:{index}:label",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        cell.x + 10.0,
                        cell.y + 12.0,
                        max(0.0, cell.width - 20.0),
                        20.0,
                    ),
                    fill=_DEFAULT_MUTED if item.disabled else _DEFAULT_FOREGROUND,
                    text=item.label,
                    font_size=13.0,
                    font_family="Segoe UI",
                    z_index=2,
                    hit_testable=False,
                )
            )
            root.add(node)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        group_nodes = []
        for group_index, group in enumerate(self._groups):
            command_nodes = tuple(
                AccessibilityNode(
                    key=f"{self.key}:a11y:group:{group_index}:command:{index}",
                    role=AccessibilityRole.BUTTON,
                    name=item.label,
                    description=item.shortcut,
                    enabled=self.enabled and not item.disabled,
                    focusable=False,
                    focused=False,
                    active=(
                        group_index == self._selected_index
                        and index == self._active_command_index
                    ),
                )
                for index, item in enumerate(group.items)
            )
            group_nodes.append(
                AccessibilityNode(
                    key=f"{self.key}:a11y:group:{group_index}",
                    role=AccessibilityRole.GROUP,
                    name=group.label,
                    description=None,
                    enabled=self.enabled,
                    focusable=False,
                    focused=False,
                    selected=group_index == self._selected_index,
                    active=group_index == self._selected_index,
                    children=command_nodes,
                )
            )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=tuple(group_nodes),
        )

    def _initial_group_index(self, selected_key: Hashable | None) -> int | None:
        if not self._groups:
            return None
        if selected_key is None:
            return 0
        index = _index_for_group_key(self._groups, selected_key)
        if index is None:
            raise KeyError(f"Unknown selected ribbon group key: {selected_key!r}")
        return index

    def _first_active_command(self) -> int | None:
        group = self.selected_group
        if group is None:
            return None
        return _first_enabled(group.items)

    def _sync_accessibility(self) -> None:
        group = self.selected_group
        command = self.active_command
        if group is None:
            self.accessible_value_text = "No ribbon group selected"
        elif command is None:
            self.accessible_value_text = f"{group.label}; no enabled command"
        else:
            self.accessible_value_text = f"{group.label}; {command.label}"

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
        if platform_event.y < self.bounds.y + self._tab_height:
            index = int((platform_event.x - self.bounds.x) // self._tab_width)
            if 0 <= index < len(self._groups):
                self.select_group(self._groups[index].key)
                event.prevent_default()
            return
        group = self.selected_group
        if group is None:
            return
        index = int((platform_event.x - self.bounds.x) // self._command_width)
        if 0 <= index < len(group.items):
            self.activate_command(group.items[index].key)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._groups:
            return
        if platform_event.alt or platform_event.ctrl or platform_event.meta:
            return
        key_code = platform_event.key_code
        if key_code in {_VK_LEFT, _VK_RIGHT, _VK_HOME, _VK_END}:
            if key_code == _VK_HOME:
                target = 0
            elif key_code == _VK_END:
                target = len(self._groups) - 1
            else:
                current = self._selected_index or 0
                step = -1 if key_code == _VK_LEFT else 1
                target = (current + step) % len(self._groups)
            self.select_group(self._groups[target].key)
            event.prevent_default()
            return

        group = self.selected_group
        if group is None or not group.items:
            return
        if key_code in {_VK_UP, _VK_DOWN}:
            target = _next_enabled(
                group.items,
                self._active_command_index,
                -1 if key_code == _VK_UP else 1,
            )
            if target is not None:
                self._active_command_index = target
                self._sync_accessibility()
                self.invalidate(reason="selection")
                event.prevent_default()
            return
        if key_code in {_VK_RETURN, _VK_SPACE} and self._active_command_index is not None:
            self.activate_command(group.items[self._active_command_index].key)
            event.prevent_default()


def _validate_items(items: Sequence[CommandItem]) -> tuple[CommandItem, ...]:
    normalized = tuple(items)
    keys: set[Hashable] = set()
    for item in normalized:
        if not isinstance(item, CommandItem):
            raise TypeError("Command surfaces require CommandItem values.")
        if item.key in keys:
            raise ValueError(f"Duplicate command key: {item.key!r}")
        keys.add(item.key)
    return normalized


def _validate_groups(groups: Sequence[RibbonGroup]) -> tuple[RibbonGroup, ...]:
    normalized = tuple(groups)
    keys: set[Hashable] = set()
    for group in normalized:
        if not isinstance(group, RibbonGroup):
            raise TypeError("Ribbon groups must be RibbonGroup values.")
        if group.key in keys:
            raise ValueError(f"Duplicate ribbon group key: {group.key!r}")
        keys.add(group.key)
    return normalized


def _index_for_key(
    items: Sequence[CommandItem],
    key: Hashable | None,
) -> int | None:
    if key is None:
        return None
    return next((index for index, item in enumerate(items) if item.key == key), None)


def _index_for_group_key(
    groups: Sequence[RibbonGroup],
    key: Hashable | None,
) -> int | None:
    if key is None:
        return None
    return next((index for index, group in enumerate(groups) if group.key == key), None)


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


__all__ = [
    "CommandItem",
    "MenuBar",
    "Ribbon",
    "RibbonGroup",
    "Toolbar",
]
