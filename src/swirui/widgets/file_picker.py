"""Retained file and folder picker widgets for SwirUI."""

from __future__ import annotations

import fnmatch
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_BACK, _VK_RETURN, _VK_SPACE = 0x08, 0x0D, 0x20
_VK_PRIOR, _VK_NEXT, _VK_END, _VK_HOME = 0x21, 0x22, 0x23, 0x24
_VK_UP, _VK_DOWN = 0x26, 0x28
_BG = Color.from_hex("#06101A")
_SURFACE = Color.from_hex("#091722")
_ROW = Color.from_hex("#07131D")
_SELECTED = Color.from_hex("#0B3550")
_TEXT = Color.from_hex("#E9F8FF")
_MUTED = Color.from_hex("#8DA8B8")
_ACCENT = Color.from_hex("#62E5FF")


@dataclass(frozen=True, slots=True)
class FileFilter:
    """Named filename-pattern filter used by :class:`FilePicker`."""

    name: str
    patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        name = self.name.strip()
        patterns = tuple(p.strip() for p in self.patterns if p.strip())
        if not name:
            raise ValueError("FileFilter.name must not be empty.")
        if not patterns:
            raise ValueError("FileFilter.patterns must contain at least one pattern.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "patterns", patterns)

    def matches(self, path: Path) -> bool:
        name = path.name.casefold()
        return any(fnmatch.fnmatchcase(name, pattern.casefold()) for pattern in self.patterns)


@dataclass(frozen=True, slots=True)
class FilePickerEntry:
    """Immutable filesystem entry snapshot exposed by retained pickers."""

    path: Path
    name: str
    is_directory: bool
    size: int | None = None


class _PathPicker(Widget):
    _HEADER = 44.0
    _FOOTER = 46.0
    _PAD = 8.0
    _ACTION = 126.0

    def __init__(
        self,
        *,
        bounds: Rect,
        directory: str | Path | None,
        folders_only: bool,
        filters: Sequence[FileFilter] = (),
        active_filter_index: int = 0,
        show_hidden: bool = False,
        row_height: float = 30.0,
        key: str | None = None,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str,
        accessible_description: str | None = None,
    ) -> None:
        self._folders_only = folders_only
        self._filters = tuple(filters)
        if any(not isinstance(item, FileFilter) for item in self._filters):
            raise TypeError("filters must contain FileFilter values.")
        if folders_only and self._filters:
            raise ValueError("FolderPicker does not accept file filters.")
        self._filter_index = int(active_filter_index)
        if self._filters:
            if not 0 <= self._filter_index < len(self._filters):
                raise IndexError("active_filter_index is out of range.")
        elif self._filter_index != 0:
            raise IndexError("active_filter_index must be 0 when no filters are configured.")
        self._show_hidden = bool(show_hidden)
        self._row_height = float(row_height)
        if not math.isfinite(self._row_height) or self._row_height <= 0.0:
            raise ValueError("row_height must be finite and positive.")
        self._font = font_family.strip()
        if not self._font:
            raise ValueError("font_family must not be empty.")
        self._directory = self._directory_path(directory)
        self._entries: tuple[FilePickerEntry, ...] = ()
        self._selected: int | None = None
        self._scroll = 0
        self._error: str | None = None
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
        self.on("pointer_down", self._pointer_down)
        self.on("pointer_scroll", self._pointer_scroll)
        self.on("key_down", self._key_down)
        self.refresh()

    @property
    def current_directory(self) -> Path:
        return self._directory

    @property
    def entries(self) -> tuple[FilePickerEntry, ...]:
        return self._entries

    @property
    def filters(self) -> tuple[FileFilter, ...]:
        return self._filters

    @property
    def active_filter_index(self) -> int:
        return self._filter_index

    @property
    def active_filter(self) -> FileFilter | None:
        return self._filters[self._filter_index] if self._filters else None

    @property
    def show_hidden(self) -> bool:
        return self._show_hidden

    @property
    def selected_index(self) -> int | None:
        return self._selected

    @property
    def selected_entry(self) -> FilePickerEntry | None:
        return None if self._selected is None else self._entries[self._selected]

    @property
    def selected_path(self) -> Path | None:
        entry = self.selected_entry
        return None if entry is None else entry.path

    @property
    def scroll_row(self) -> int:
        return self._scroll

    @property
    def row_height(self) -> float:
        return self._row_height

    @property
    def last_error(self) -> str | None:
        return self._error

    def set_active_filter(self, index: int) -> Self:
        normalized = int(index)
        if not 0 <= normalized < len(self._filters):
            raise IndexError("active_filter_index is out of range.")
        if normalized != self._filter_index:
            self._filter_index = normalized
            self.refresh()
            self.emit("filter_changed", index=normalized, filter=self.active_filter)
        return self

    def set_show_hidden(self, show_hidden: bool) -> Self:
        if bool(show_hidden) != self._show_hidden:
            self._show_hidden = bool(show_hidden)
            self.refresh()
        return self

    def navigate_to(self, directory: str | Path) -> Self:
        target = self._directory_path(directory)
        if target != self._directory:
            previous = self._directory
            self._directory = target
            self._selected = None
            self._scroll = 0
            self.refresh(preserve_selection=False)
            self.emit("directory_changed", directory=target, previous=previous)
        return self

    def navigate_parent(self) -> Self:
        parent = self._directory.parent
        return self if parent == self._directory else self.navigate_to(parent)

    def refresh(self, *, preserve_selection: bool = True) -> Self:
        previous = self.selected_path if preserve_selection else None
        try:
            entries = self._scan()
        except OSError as exc:
            entries = ()
            self._error = str(exc)
            self.emit("filesystem_error", directory=self._directory, error=exc)
        else:
            self._error = None
        self._entries = entries
        self._selected = self._find(previous)
        if self._selected is None:
            self._selected = 0 if entries else None
        self._scroll = max(0, min(self._scroll, self._max_scroll()))
        self._ensure_visible()
        self._sync_a11y()
        self.invalidate(reason="filesystem")
        self.emit("entries_changed", directory=self._directory, count=len(entries))
        return self

    def select_index(self, index: int) -> Self:
        normalized = int(index)
        if not 0 <= normalized < len(self._entries):
            raise IndexError("Picker entry index is out of range.")
        if normalized != self._selected:
            previous = self.selected_entry
            self._selected = normalized
            self._ensure_visible()
            self._sync_a11y()
            self.invalidate(reason="selection")
            entry = self._entries[normalized]
            self.emit(
                "selection_changed",
                index=normalized,
                path=entry.path,
                entry=entry,
                previous=previous,
            )
        return self

    def select_path(self, path: str | Path) -> Self:
        index = self._find(Path(path).expanduser().absolute())
        if index is None:
            raise KeyError(f"Path is not present in the current picker view: {path}")
        return self.select_index(index)

    def activate_selected(self) -> Self:
        entry = self.selected_entry
        if entry is None:
            return self
        if entry.is_directory:
            return self.navigate_to(entry.path)
        return self.confirm_selection()

    def confirm_selection(self) -> Self:
        path = self._confirmation()
        if path is not None:
            self.emit(
                "selection_confirmed",
                path=path,
                directory=self._directory,
                entry=self.selected_entry,
            )
        return self

    def body_bounds(self) -> Rect:
        return Rect(
            self.bounds.x + self._PAD,
            self.bounds.y + self._HEADER,
            max(0.0, self.bounds.width - self._PAD * 2.0),
            max(0.0, self.bounds.height - self._HEADER - self._FOOTER),
        )

    def action_bounds(self) -> Rect:
        width = min(self._ACTION, max(0.0, self.bounds.width - self._PAD * 2.0))
        return Rect(
            self.bounds.right - self._PAD - width,
            self.bounds.bottom - self._FOOTER + 7.0,
            width,
            32.0,
        )

    def row_bounds(self, index: int) -> Rect:
        if not 0 <= index < len(self._entries):
            raise IndexError("Picker entry index is out of range.")
        body = self.body_bounds()
        return Rect(
            body.x,
            body.y + (index - self._scroll) * self._row_height,
            body.width,
            self._row_height,
        )

    def visible_range(self) -> range:
        return range(self._scroll, min(len(self._entries), self._scroll + self._capacity()))

    def build_scene_node(self) -> SceneNode:
        root = self._rect(self.key, self.bounds, _BG, True, 10.0)
        header = Rect(self.bounds.x, self.bounds.y, self.bounds.width, self._HEADER)
        body = self.body_bounds()
        footer = Rect(
            self.bounds.x,
            self.bounds.bottom - self._FOOTER,
            self.bounds.width,
            self._FOOTER,
        )
        root.add(
            self._rect(f"{self.key}:header", header, _SURFACE),
            self._rect(f"{self.key}:body", body, _BG),
            self._rect(f"{self.key}:footer", footer, _SURFACE),
            self._text(
                f"{self.key}:path",
                Rect(header.x + 12.0, header.y + 12.0, max(0.0, header.width - 24.0), 20.0),
                str(self._directory),
                _TEXT,
            ),
        )
        for index in self.visible_range():
            entry = self._entries[index]
            row = self.row_bounds(index)
            root.add(
                self._rect(
                    f"{self.key}:row:{index}",
                    row,
                    _SELECTED if index == self._selected else _ROW,
                    radius=4.0,
                ),
                self._text(
                    f"{self.key}:row:{index}:name",
                    Rect(row.x + 12.0, row.y + 6.0, max(0.0, row.width - 24.0), 19.0),
                    entry.name,
                    _TEXT,
                ),
            )
        action = self.action_bounds()
        root.add(
            self._rect(f"{self.key}:action", action, _ACCENT.with_alpha(0.22), radius=6.0),
            self._text(
                f"{self.key}:action-label",
                Rect(action.x + 10.0, action.y + 7.0, max(0.0, action.width - 20.0), 18.0),
                "Select Folder" if self._folders_only else "Open",
                _TEXT if self._confirmation() is not None else _MUTED,
            ),
        )
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(self._a11y_entry(index) for index in self.visible_range())
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.LIST,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            row_count=len(self._entries),
            children=children,
        )

    def _scan(self) -> tuple[FilePickerEntry, ...]:
        result: list[FilePickerEntry] = []
        active_filter = self.active_filter
        for path in self._directory.iterdir():
            if not self._show_hidden and path.name.startswith("."):
                continue
            try:
                directory = path.is_dir()
            except OSError:
                continue
            if self._folders_only and not directory:
                continue
            if not directory and active_filter is not None and not active_filter.matches(path):
                continue
            size: int | None = None
            if not directory:
                try:
                    size = path.stat().st_size
                except OSError:
                    size = None
            result.append(FilePickerEntry(path.absolute(), path.name, directory, size))
        result.sort(key=lambda item: (not item.is_directory, item.name.casefold(), item.name))
        return tuple(result)

    def _pointer_down(self, event: Event) -> None:
        native = self._native_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or native is None
            or native.button is not PointerButton.LEFT
            or native.x is None
            or native.y is None
        ):
            return
        if self._contains(self.action_bounds(), native.x, native.y):
            self.confirm_selection()
            event.prevent_default()
            return
        body = self.body_bounds()
        if not self._contains(body, native.x, native.y):
            return
        index = self._scroll + int((native.y - body.y) // self._row_height)
        if 0 <= index < len(self._entries):
            entry = self._entries[index]
            if index == self._selected and entry.is_directory:
                self.navigate_to(entry.path)
            else:
                self.select_index(index)
            event.prevent_default()

    def _pointer_scroll(self, event: Event) -> None:
        native = self._native_event(event, PlatformEventKind.POINTER_SCROLL)
        if not self.enabled or native is None or native.delta_y == 0.0:
            return
        rows = max(1, round(abs(native.delta_y) / max(1.0, self._row_height)))
        before = self._scroll
        self._scroll += rows if native.delta_y > 0.0 else -rows
        self._scroll = max(0, min(self._scroll, self._max_scroll()))
        if self._scroll != before:
            self.invalidate(reason="scroll")
            event.prevent_default()

    def _key_down(self, event: Event) -> None:
        native = self._native_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or native is None or native.alt or native.meta:
            return
        key = native.key_code
        if key == _VK_BACK:
            self.navigate_parent()
        elif key == _VK_SPACE or (key == _VK_RETURN and native.ctrl):
            self.confirm_selection()
        elif key == _VK_RETURN:
            self.activate_selected()
        else:
            target = self._key_target(key)
            if target is None:
                return
            self.select_index(target)
        event.prevent_default()

    def _key_target(self, key: int | None) -> int | None:
        if not self._entries:
            return None
        if key == _VK_HOME:
            return 0
        if key == _VK_END:
            return len(self._entries) - 1
        if key not in {_VK_UP, _VK_DOWN, _VK_PRIOR, _VK_NEXT}:
            return None
        current = self._selected or 0
        if key in {_VK_PRIOR, _VK_NEXT}:
            step = max(1, self._capacity() - 1)
            step = -step if key == _VK_PRIOR else step
        else:
            step = -1 if key == _VK_UP else 1
        return max(0, min(len(self._entries) - 1, current + step))

    def _confirmation(self) -> Path | None:
        entry = self.selected_entry
        if self._folders_only:
            return entry.path if entry is not None and entry.is_directory else self._directory
        return None if entry is None or entry.is_directory else entry.path

    def _find(self, path: Path | None) -> int | None:
        if path is None:
            return None
        target = path.absolute()
        return next((i for i, entry in enumerate(self._entries) if entry.path == target), None)

    def _capacity(self) -> int:
        height = self.body_bounds().height
        return 0 if height <= 0.0 else max(1, math.ceil(height / self._row_height))

    def _max_scroll(self) -> int:
        return max(0, len(self._entries) - self._capacity())

    def _ensure_visible(self) -> None:
        if self._selected is None or self._capacity() <= 0:
            return
        if self._selected < self._scroll:
            self._scroll = self._selected
        elif self._selected >= self._scroll + self._capacity():
            self._scroll = self._selected - self._capacity() + 1
        self._scroll = max(0, min(self._scroll, self._max_scroll()))

    def _sync_a11y(self) -> None:
        selected = self._confirmation()
        self.accessible_value_text = str(selected or self._directory)

    def _a11y_entry(self, index: int) -> AccessibilityNode:
        entry = self._entries[index]
        return AccessibilityNode(
            key=f"{self.key}:a11y:{index}",
            role=AccessibilityRole.LIST_ITEM,
            name=entry.name,
            description="Folder" if entry.is_directory else "File",
            enabled=self.enabled,
            focusable=False,
            focused=False,
            selected=index == self._selected,
            active=index == self._selected,
            row_index=index,
            row_count=len(self._entries),
            value_text=str(entry.path),
        )

    def _rect(
        self,
        key: str,
        bounds: Rect,
        fill: Color,
        hit_testable: bool = False,
        radius: float = 0.0,
    ) -> SceneNode:
        return SceneNode(
            key=key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=bounds,
            fill=fill,
            opacity=self.opacity,
            corner_radius=CornerRadius.uniform(radius),
            hit_testable=hit_testable,
            clip_to_bounds=key == self.key,
        )

    def _text(self, key: str, bounds: Rect, text: str, color: Color) -> SceneNode:
        return SceneNode(
            key=key,
            kind=SceneNodeKind.TEXT,
            bounds=bounds,
            fill=color,
            text=text,
            font_size=12.0,
            font_family=self._font,
            z_index=2,
            hit_testable=False,
        )

    @staticmethod
    def _contains(bounds: Rect, x: float, y: float) -> bool:
        return bounds.x <= x < bounds.right and bounds.y <= y < bounds.bottom

    @staticmethod
    def _native_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        candidate = event.data.get("event")
        if isinstance(candidate, PlatformEvent) and candidate.kind is kind:
            return candidate
        return None

    @staticmethod
    def _directory_path(directory: str | Path | None) -> Path:
        path = Path.cwd() if directory is None else Path(directory).expanduser()
        path = path.absolute()
        if not path.exists():
            raise FileNotFoundError(f"Picker directory does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Picker path is not a directory: {path}")
        return path


class FilePicker(_PathPicker):
    """Retained filesystem browser that confirms file selections."""

    def __init__(
        self,
        *,
        bounds: Rect,
        directory: str | Path | None = None,
        filters: Sequence[FileFilter] = (),
        active_filter_index: int = 0,
        show_hidden: bool = False,
        row_height: float = 30.0,
        key: str | None = None,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "File picker",
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            directory=directory,
            folders_only=False,
            filters=filters,
            active_filter_index=active_filter_index,
            show_hidden=show_hidden,
            row_height=row_height,
            key=key,
            font_family=font_family,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )


class FolderPicker(_PathPicker):
    """Retained filesystem browser that confirms folder selections."""

    def __init__(
        self,
        *,
        bounds: Rect,
        directory: str | Path | None = None,
        show_hidden: bool = False,
        row_height: float = 30.0,
        key: str | None = None,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Folder picker",
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            directory=directory,
            folders_only=True,
            show_hidden=show_hidden,
            row_height=row_height,
            key=key,
            font_family=font_family,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    @property
    def selected_folder(self) -> Path:
        path = self._confirmation()
        assert path is not None
        return path
