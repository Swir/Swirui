"""Retained professional file and folder pickers for SwirUI."""

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

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_BACK = 0x08
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_UP = 0x26
_VK_DOWN = 0x28

_BACKGROUND = Color.from_hex("#06101A")
_SURFACE = Color.from_hex("#091722")
_ROW = Color.from_hex("#07131D")
_ROW_SELECTED = Color.from_hex("#0B3550")
_BORDER = Color.from_hex("#164D6B")
_FOREGROUND = Color.from_hex("#E9F8FF")
_MUTED = Color.from_hex("#8DA8B8")
_ACCENT = Color.from_hex("#62E5FF")
_DISABLED = Color.from_hex("#456273")


@dataclass(frozen=True, slots=True)
class FileFilter:
    """Named filename-pattern filter used by :class:`FilePicker`."""

    name: str
    patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        name = self.name.strip()
        patterns = tuple(pattern.strip() for pattern in self.patterns if pattern.strip())
        if not name:
            raise ValueError("FileFilter.name must not be empty.")
        if not patterns:
            raise ValueError("FileFilter.patterns must contain at least one pattern.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "patterns", patterns)

    def matches(self, path: Path) -> bool:
        """Return whether ``path`` matches at least one configured pattern."""

        name = path.name.casefold()
        return any(fnmatch.fnmatchcase(name, pattern.casefold()) for pattern in self.patterns)


@dataclass(frozen=True, slots=True)
class FilePickerEntry:
    """Immutable filesystem entry snapshot used by retained pickers."""

    path: Path
    name: str
    is_directory: bool
    size: int | None = None


class _PathPicker(Widget):
    _HEADER_HEIGHT = 44.0
    _FOOTER_HEIGHT = 46.0
    _PADDING = 8.0
    _ACTION_WIDTH = 126.0

    def __init__(
        self,
        *,
        bounds: Rect,
        directory: str | Path | None,
        select_directories: bool,
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
        self._select_directories = bool(select_directories)
        self._filters = self._validate_filters(filters)
        if self._select_directories and self._filters:
            raise ValueError("FolderPicker does not accept file filters.")
        self._active_filter_index = self._normalize_filter_index(active_filter_index)
        self._show_hidden = bool(show_hidden)
        self._row_height = self._positive(row_height, "row_height")
        family = str(font_family).strip()
        if not family:
            raise ValueError("font_family must not be empty.")
        self._font_family = family
        self._current_directory = self._normalize_directory(directory)
        self._entries: tuple[FilePickerEntry, ...] = ()
        self._selected_index: int | None = None
        self._scroll_row = 0
        self._last_error: str | None = None
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
        self.on("pointer_scroll", self._on_pointer_scroll)
        self.on("key_down", self._on_key_down)
        self.refresh()

    @property
    def current_directory(self) -> Path:
        return self._current_directory

    @property
    def entries(self) -> tuple[FilePickerEntry, ...]:
        return self._entries

    @property
    def filters(self) -> tuple[FileFilter, ...]:
        return self._filters

    @property
    def active_filter_index(self) -> int:
        return self._active_filter_index

    @property
    def active_filter(self) -> FileFilter | None:
        if not self._filters:
            return None
        return self._filters[self._active_filter_index]

    @property
    def show_hidden(self) -> bool:
        return self._show_hidden

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_entry(self) -> FilePickerEntry | None:
        if self._selected_index is None:
            return None
        return self._entries[self._selected_index]

    @property
    def selected_path(self) -> Path | None:
        entry = self.selected_entry
        return None if entry is None else entry.path

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def scroll_row(self) -> int:
        return self._scroll_row

    @property
    def row_height(self) -> float:
        return self._row_height

    def set_active_filter(self, index: int) -> Self:
        normalized = self._normalize_filter_index(index)
        if normalized == self._active_filter_index:
            return self
        self._active_filter_index = normalized
        self.refresh()
        self.emit("filter_changed", index=normalized, filter=self.active_filter)
        return self

    def set_show_hidden(self, show_hidden: bool) -> Self:
        normalized = bool(show_hidden)
        if normalized == self._show_hidden:
            return self
        self._show_hidden = normalized
        self.refresh()
        return self

    def navigate_to(self, directory: str | Path) -> Self:
        target = self._normalize_directory(directory)
        if target == self._current_directory:
            return self
        previous = self._current_directory
        self._current_directory = target
        self._selected_index = None
        self._scroll_row = 0
        self.refresh(preserve_selection=False)
        self.emit("directory_changed", directory=target, previous=previous)
        return self

    def navigate_parent(self) -> Self:
        parent = self._current_directory.parent
        if parent == self._current_directory:
            return self
        return self.navigate_to(parent)

    def refresh(self, *, preserve_selection: bool = True) -> Self:
        selected_path = self.selected_path if preserve_selection else None
        try:
            entries = self._scan_directory(self._current_directory)
        except OSError as exc:
            self._last_error = str(exc)
            entries = ()
            self.emit("filesystem_error", directory=self._current_directory, error=exc)
        else:
            self._last_error = None
        self._entries = entries
        self._selected_index = self._index_for_path(selected_path)
        if self._selected_index is None:
            self._selected_index = self._first_selectable_index()
        self._clamp_scroll()
        self._ensure_selection_visible()
        self._sync_accessibility_value()
        self.invalidate(reason="filesystem")
        self.emit("entries_changed", directory=self._current_directory, count=len(entries))
        return self

    def select_index(self, index: int) -> Self:
        normalized = self._normalize_index(index)
        entry = self._entries[normalized]
        if not self._entry_selectable(entry) or normalized == self._selected_index:
            return self
        previous = self.selected_entry
        self._selected_index = normalized
        self._ensure_selection_visible()
        self._sync_accessibility_value()
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=normalized,
            path=entry.path,
            entry=entry,
            previous=previous,
        )
        return self

    def select_path(self, path: str | Path) -> Self:
        target = Path(path).expanduser().absolute()
        index = self._index_for_path(target)
        if index is None:
            raise KeyError(f"Path is not present in the current picker view: {target}")
        return self.select_index(index)

    def activate_selected(self) -> Self:
        entry = self.selected_entry
        if entry is None:
            return self
        if entry.is_directory:
            self.navigate_to(entry.path)
        elif not self._select_directories:
            self.confirm_selection()
        return self

    def confirm_selection(self) -> Self:
        path = self._confirmation_path()
        if path is None:
            return self
        self.emit(
            "selection_confirmed",
            path=path,
            directory=self._current_directory,
            entry=self.selected_entry,
        )
        return self

    def body_bounds(self) -> Rect:
        return Rect(
            self.bounds.x + self._PADDING,
            self.bounds.y + self._HEADER_HEIGHT,
            max(0.0, self.bounds.width - self._PADDING * 2.0),
            max(0.0, self.bounds.height - self._HEADER_HEIGHT - self._FOOTER_HEIGHT),
        )

    def action_bounds(self) -> Rect:
        return Rect(
            max(
                self.bounds.x + self._PADDING,
                self.bounds.right - self._PADDING - self._ACTION_WIDTH,
            ),
            self.bounds.bottom - self._FOOTER_HEIGHT + 7.0,
            min(self._ACTION_WIDTH, max(0.0, self.bounds.width - self._PADDING * 2.0)),
            32.0,
        )

    def row_bounds(self, index: int) -> Rect:
        normalized = self._normalize_index(index)
        body = self.body_bounds()
        return Rect(
            body.x,
            body.y + (normalized - self._scroll_row) * self._row_height,
            body.width,
            self._row_height,
        )

    def visible_range(self) -> range:
        capacity = self._visible_capacity()
        stop = min(len(self._entries), self._scroll_row + capacity)
        return range(self._scroll_row, stop)

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
        self._append_header(root)
        self._append_rows(root)
        self._append_footer(root)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(
            self._accessibility_entry(index, self._entries[index])
            for index in self.visible_range()
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
            row_count=len(self._entries),
            children=children,
        )

    def _accessibility_entry(
        self,
        index: int,
        entry: FilePickerEntry,
    ) -> AccessibilityNode:
        return AccessibilityNode(
            key=f"{self.key}:a11y:entry:{index}",
            role=AccessibilityRole.LIST_ITEM,
            name=entry.name,
            description="Folder" if entry.is_directory else "File",
            enabled=self.enabled and self._entry_selectable(entry),
            focusable=False,
            focused=False,
            selected=index == self._selected_index,
            active=index == self._selected_index,
            row_index=index,
            row_count=len(self._entries),
            value_text=str(entry.path),
        )

    def _append_header(self, root: SceneNode) -> None:
        header = Rect(
            self.bounds.x,
            self.bounds.y,
            self.bounds.width,
            self._HEADER_HEIGHT,
        )
        root.add(
            SceneNode(
                key=f"{self.key}:header",
                kind=SceneNodeKind.RECTANGLE,
                bounds=header,
                fill=_SURFACE,
                z_index=1,
                hit_testable=False,
            )
        )
        parent_enabled = self._current_directory.parent != self._current_directory
        parent_bounds = Rect(header.x + 8.0, header.y + 7.0, 32.0, 30.0)
        root.add(
            SceneNode(
                key=f"{self.key}:parent-button",
                kind=SceneNodeKind.RECTANGLE,
                bounds=parent_bounds,
                fill=_BORDER if parent_enabled else _BACKGROUND,
                corner_radius=CornerRadius.uniform(6.0),
                z_index=2,
                hit_testable=False,
            ),
            self._text_node(
                f"{self.key}:parent-label",
                Rect(parent_bounds.x + 9.0, parent_bounds.y + 4.0, 20.0, 20.0),
                "↑",
                17.0,
                _FOREGROUND if parent_enabled else _DISABLED,
                3,
            ),
            self._text_node(
                f"{self.key}:path",
                Rect(header.x + 50.0, header.y + 12.0, max(0.0, header.width - 60.0), 20.0),
                self._elide_middle(
                    str(self._current_directory),
                    max(12, int((header.width - 64.0) / 7.5)),
                ),
                12.0,
                _FOREGROUND,
                3,
            ),
        )

    def _append_rows(self, root: SceneNode) -> None:
        body = self.body_bounds()
        root.add(
            SceneNode(
                key=f"{self.key}:body",
                kind=SceneNodeKind.RECTANGLE,
                bounds=body,
                fill=_BACKGROUND,
                z_index=1,
                hit_testable=False,
            )
        )
        if self._last_error is not None:
            root.add(
                self._text_node(
                    f"{self.key}:error",
                    Rect(body.x + 12.0, body.y + 12.0, max(0.0, body.width - 24.0), 22.0),
                    self._elide_middle(self._last_error, max(16, int(body.width / 7.5))),
                    12.0,
                    _DISABLED,
                    4,
                )
            )
            return
        if not self._entries:
            root.add(
                self._text_node(
                    f"{self.key}:empty",
                    Rect(body.x + 12.0, body.y + 12.0, max(0.0, body.width - 24.0), 22.0),
                    "No matching folders" if self._select_directories else "No matching files",
                    12.0,
                    _MUTED,
                    4,
                )
            )
            return
        for index in self.visible_range():
            entry = self._entries[index]
            row = self.row_bounds(index)
            selected = index == self._selected_index
            root.add(
                SceneNode(
                    key=f"{self.key}:row:{index}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=row,
                    fill=_ROW_SELECTED if selected else _ROW,
                    corner_radius=CornerRadius.uniform(4.0),
                    z_index=2,
                    hit_testable=False,
                )
            )
            kind_label = "DIR" if entry.is_directory else self._file_kind(entry)
            root.add(
                self._text_node(
                    f"{self.key}:row:{index}:kind",
                    Rect(row.x + 8.0, row.y + 7.0, 42.0, 18.0),
                    kind_label,
                    10.0,
                    _ACCENT if entry.is_directory else _MUTED,
                    4,
                ),
                self._text_node(
                    f"{self.key}:row:{index}:name",
                    Rect(row.x + 54.0, row.y + 6.0, max(0.0, row.width - 144.0), 19.0),
                    self._elide_middle(entry.name, max(8, int((row.width - 144.0) / 7.0))),
                    12.0,
                    _FOREGROUND,
                    4,
                ),
            )
            if not entry.is_directory:
                root.add(
                    self._text_node(
                        f"{self.key}:row:{index}:size",
                        Rect(row.right - 84.0, row.y + 7.0, 76.0, 18.0),
                        self._format_size(entry.size),
                        10.0,
                        _MUTED,
                        4,
                    )
                )

    def _append_footer(self, root: SceneNode) -> None:
        footer = Rect(
            self.bounds.x,
            self.bounds.bottom - self._FOOTER_HEIGHT,
            self.bounds.width,
            self._FOOTER_HEIGHT,
        )
        root.add(
            SceneNode(
                key=f"{self.key}:footer",
                kind=SceneNodeKind.RECTANGLE,
                bounds=footer,
                fill=_SURFACE,
                z_index=1,
                hit_testable=False,
            )
        )
        action = self.action_bounds()
        enabled = self._confirmation_path() is not None
        root.add(
            SceneNode(
                key=f"{self.key}:action",
                kind=SceneNodeKind.RECTANGLE,
                bounds=action,
                fill=_ACCENT.with_alpha(0.22) if enabled else _BACKGROUND,
                corner_radius=CornerRadius.uniform(6.0),
                z_index=2,
                hit_testable=False,
            ),
            self._text_node(
                f"{self.key}:action-label",
                Rect(action.x + 14.0, action.y + 7.0, max(0.0, action.width - 28.0), 19.0),
                "Select Folder" if self._select_directories else "Open",
                12.0,
                _FOREGROUND if enabled else _DISABLED,
                4,
            ),
        )
        status_width = max(0.0, action.x - footer.x - 20.0)
        root.add(
            self._text_node(
                f"{self.key}:status",
                Rect(footer.x + 10.0, footer.y + 8.0, status_width, 18.0),
                self._footer_status(),
                10.0,
                _MUTED,
                4,
            )
        )
        if self.active_filter is not None:
            root.add(
                self._text_node(
                    f"{self.key}:filter",
                    Rect(footer.x + 10.0, footer.y + 24.0, status_width, 16.0),
                    f"Filter: {self.active_filter.name}",
                    10.0,
                    _MUTED,
                    4,
                )
            )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
        ):
            return
        x = platform_event.x
        y = platform_event.y
        if not self._contains(self.bounds, x, y):
            return
        parent_bounds = Rect(self.bounds.x + 8.0, self.bounds.y + 7.0, 32.0, 30.0)
        if self._contains(parent_bounds, x, y):
            self.navigate_parent()
            event.prevent_default()
            return
        if self._contains(self.action_bounds(), x, y):
            self.confirm_selection()
            event.prevent_default()
            return
        body = self.body_bounds()
        if not self._contains(body, x, y):
            return
        relative = int((y - body.y) // self._row_height)
        index = self._scroll_row + relative
        if not 0 <= index < len(self._entries):
            return
        entry = self._entries[index]
        if not self._entry_selectable(entry):
            return
        if index == self._selected_index and entry.is_directory:
            self.navigate_to(entry.path)
        else:
            self.select_index(index)
        event.prevent_default()

    def _on_pointer_scroll(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_SCROLL)
        if not self.enabled or platform_event is None or platform_event.delta_y == 0.0:
            return
        rows = max(1, round(abs(platform_event.delta_y) / max(1.0, self._row_height)))
        direction = 1 if platform_event.delta_y > 0.0 else -1
        before = self._scroll_row
        self._scroll_row += direction * rows
        self._clamp_scroll()
        if self._scroll_row != before:
            self.invalidate(reason="scroll")
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None:
            return
        if platform_event.alt or platform_event.meta:
            return
        key_code = platform_event.key_code
        if key_code == _VK_BACK:
            self.navigate_parent()
            event.prevent_default()
            return
        if key_code == _VK_SPACE or (key_code == _VK_RETURN and platform_event.ctrl):
            self.confirm_selection()
            event.prevent_default()
            return
        if key_code == _VK_RETURN:
            self.activate_selected()
            event.prevent_default()
            return
        target = self._navigation_target(key_code)
        if target is not None:
            self.select_index(target)
            event.prevent_default()

    def _navigation_target(self, key_code: int | None) -> int | None:
        if not self._entries:
            return None
        if key_code == _VK_HOME:
            return self._first_selectable_index()
        if key_code == _VK_END:
            return self._last_selectable_index()
        if key_code not in {_VK_UP, _VK_DOWN, _VK_PRIOR, _VK_NEXT}:
            return None
        if self._selected_index is None:
            return self._first_selectable_index()
        if key_code in {_VK_PRIOR, _VK_NEXT}:
            step = max(1, self._visible_capacity() - 1)
            if key_code == _VK_PRIOR:
                step = -step
        else:
            step = -1 if key_code == _VK_UP else 1
        target = max(0, min(len(self._entries) - 1, self._selected_index + step))
        direction = 1 if step > 0 else -1
        while (
            0 <= target < len(self._entries)
            and not self._entry_selectable(self._entries[target])
        ):
            target += direction
        if 0 <= target < len(self._entries):
            return target
        return self._selected_index

    def _scan_directory(self, directory: Path) -> tuple[FilePickerEntry, ...]:
        entries: list[FilePickerEntry] = []
        active_filter = self.active_filter
        for path in directory.iterdir():
            name = path.name
            if not self._show_hidden and name.startswith("."):
                continue
            try:
                is_directory = path.is_dir()
            except OSError:
                continue
            if self._select_directories and not is_directory:
                continue
            if (
                not self._select_directories
                and not is_directory
                and active_filter is not None
                and not active_filter.matches(path)
            ):
                continue
            size: int | None = None
            if not is_directory:
                try:
                    size = path.stat().st_size
                except OSError:
                    pass
            entries.append(
                FilePickerEntry(
                    path=path.absolute(),
                    name=name,
                    is_directory=is_directory,
                    size=size,
                )
            )
        entries.sort(key=lambda entry: (not entry.is_directory, entry.name.casefold(), entry.name))
        return tuple(entries)

    def _confirmation_path(self) -> Path | None:
        if self._select_directories:
            entry = self.selected_entry
            if entry is not None and entry.is_directory:
                return entry.path
            return self._current_directory
        entry = self.selected_entry
        if entry is None or entry.is_directory:
            return None
        return entry.path

    def _entry_selectable(self, entry: FilePickerEntry) -> bool:
        return entry.is_directory or not self._select_directories

    def _first_selectable_index(self) -> int | None:
        return next(
            (index for index, entry in enumerate(self._entries) if self._entry_selectable(entry)),
            None,
        )

    def _last_selectable_index(self) -> int | None:
        return next(
            (
                index
                for index in range(len(self._entries) - 1, -1, -1)
                if self._entry_selectable(self._entries[index])
            ),
            None,
        )

    def _index_for_path(self, path: Path | None) -> int | None:
        if path is None:
            return None
        target = path.absolute()
        return next(
            (index for index, entry in enumerate(self._entries) if entry.path == target),
            None,
        )

    def _normalize_index(self, index: int) -> int:
        normalized = int(index)
        if not 0 <= normalized < len(self._entries):
            raise IndexError("Picker entry index is out of range.")
        return normalized

    def _normalize_filter_index(self, index: int) -> int:
        normalized = int(index)
        if not self._filters:
            if normalized != 0:
                raise IndexError("active_filter_index must be 0 when no filters are configured.")
            return 0
        if not 0 <= normalized < len(self._filters):
            raise IndexError("active_filter_index is out of range.")
        return normalized

    def _visible_capacity(self) -> int:
        body_height = self.body_bounds().height
        if body_height <= 0.0:
            return 0
        return max(1, int(math.ceil(body_height / self._row_height)))

    def _clamp_scroll(self) -> None:
        capacity = self._visible_capacity()
        maximum = max(0, len(self._entries) - capacity)
        self._scroll_row = max(0, min(self._scroll_row, maximum))

    def _ensure_selection_visible(self) -> None:
        if self._selected_index is None:
            return
        capacity = self._visible_capacity()
        if capacity <= 0:
            return
        if self._selected_index < self._scroll_row:
            self._scroll_row = self._selected_index
        elif self._selected_index >= self._scroll_row + capacity:
            self._scroll_row = self._selected_index - capacity + 1
        self._clamp_scroll()

    def _sync_accessibility_value(self) -> None:
        path = self._confirmation_path()
        self.accessible_value_text = (
            f"{self._current_directory}; no file selected" if path is None else str(path)
        )

    def _footer_status(self) -> str:
        entry = self.selected_entry
        if entry is None:
            return f"{len(self._entries)} items"
        kind = "folder" if entry.is_directory else "file"
        return f"{entry.name} · {kind}"

    def _text_node(
        self,
        key: str,
        bounds: Rect,
        text: str,
        size: float,
        color: Color,
        z_index: int,
    ) -> SceneNode:
        return SceneNode(
            key=key,
            kind=SceneNodeKind.TEXT,
            bounds=bounds,
            fill=color,
            text=text,
            font_size=size,
            font_family=self._font_family,
            z_index=z_index,
            hit_testable=False,
        )

    @staticmethod
    def _contains(bounds: Rect, x: float, y: float) -> bool:
        return bounds.x <= x < bounds.right and bounds.y <= y < bounds.bottom

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        candidate = event.data.get("event")
        if isinstance(candidate, PlatformEvent) and candidate.kind is kind:
            return candidate
        return None

    @staticmethod
    def _normalize_directory(directory: str | Path | None) -> Path:
        target = Path.cwd() if directory is None else Path(directory).expanduser()
        target = target.absolute()
        if not target.exists():
            raise FileNotFoundError(f"Picker directory does not exist: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"Picker path is not a directory: {target}")
        return target

    @staticmethod
    def _validate_filters(filters: Sequence[FileFilter]) -> tuple[FileFilter, ...]:
        normalized = tuple(filters)
        if any(not isinstance(file_filter, FileFilter) for file_filter in normalized):
            raise TypeError("filters must contain FileFilter values.")
        return normalized

    @staticmethod
    def _positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and positive.")
        return normalized

    @staticmethod
    def _file_kind(entry: FilePickerEntry) -> str:
        suffix = entry.path.suffix.lstrip(".").upper()
        return suffix[:4] if suffix else "FILE"

    @staticmethod
    def _format_size(size: int | None) -> str:
        if size is None:
            return "—"
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024.0 or unit == "TB":
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} TB"

    @staticmethod
    def _elide_middle(value: str, limit: int) -> str:
        if limit <= 3 or len(value) <= limit:
            return value[:limit]
        left = (limit - 1) // 2
        right = limit - left - 1
        return f"{value[:left]}…{value[-right:]}"


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
            select_directories=False,
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
            select_directories=True,
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
        """Return the selected folder, or the current directory when none is selected."""

        path = self._confirmation_path()
        assert path is not None
        return path
