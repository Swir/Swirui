"""Professional multi-row selection layered on the routed DataGrid."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, cast

from swirui.core import Event
from swirui.platforms import PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode

from .data_grid import DataGridColumn
from .data_grid_routed import DataGrid as _DataGrid

DataGridSelectionMode = Literal["single", "multiple"]

_ROW_NAVIGATION_KEYS = frozenset({0x23, 0x24, 0x21, 0x22, 0x26, 0x28})
_VK_A = 0x41
_VK_SPACE = 0x20


class DataGrid(_DataGrid):
    """DataGrid with backward-compatible single or professional multi-selection."""

    def __init__(
        self,
        columns: Sequence[DataGridColumn],
        rows: Sequence[Mapping[str, object]],
        *,
        bounds: Rect,
        key: str | None = None,
        row_height: float = 36.0,
        header_height: float = 40.0,
        cell_padding: float = 10.0,
        font_size: float = 14.0,
        font_family: str = "Segoe UI",
        corner_radius: float = 8.0,
        background: Color | None = None,
        header_background: Color | None = None,
        row_background: Color | None = None,
        alternate_row_background: Color | None = None,
        selected_background: Color | None = None,
        foreground: Color | None = None,
        header_foreground: Color | None = None,
        grid_line: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Data grid",
        accessible_description: str | None = None,
        selection_mode: DataGridSelectionMode = "single",
    ) -> None:
        normalized_mode = str(selection_mode).strip().lower()
        if normalized_mode not in {"single", "multiple"}:
            raise ValueError("DataGrid selection_mode must be 'single' or 'multiple'.")
        self._selection_mode = cast(DataGridSelectionMode, normalized_mode)
        self._selected_indices: set[int] = set()
        self._selection_anchor: int | None = None
        self._pointer_extend_selection = False
        self._pointer_toggle_selection = False
        self._keyboard_extend_selection = False

        super().__init__(
            columns,
            rows,
            bounds=bounds,
            key=key,
            row_height=row_height,
            header_height=header_height,
            cell_padding=cell_padding,
            font_size=font_size,
            font_family=font_family,
            corner_radius=corner_radius,
            background=background,
            header_background=header_background,
            row_background=row_background,
            alternate_row_background=alternate_row_background,
            selected_background=selected_background,
            foreground=foreground,
            header_foreground=header_foreground,
            grid_line=grid_line,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._sync_accessible_selection()

    @property
    def selection_mode(self) -> DataGridSelectionMode:
        """Return the configured row selection mode."""

        return self._selection_mode

    @property
    def selected_indices(self) -> tuple[int, ...]:
        """Return selected row indices in deterministic visual order."""

        return tuple(sorted(self._selected_indices))

    @property
    def selected_rows(self) -> tuple[Mapping[str, object], ...]:
        """Return selected immutable row snapshots in visual order."""

        return tuple(self.rows[index] for index in self.selected_indices)

    def select_row(
        self,
        index: int | None,
        *,
        ensure_visible: bool = True,
        extend: bool = False,
        toggle: bool = False,
    ) -> DataGrid:
        """Select a row, optionally extending or toggling in multiple mode."""

        normalized = self._normalize_selection_index(index)
        if self._selection_mode == "single":
            extend = False
            toggle = False
        else:
            extend = extend or self._pointer_extend_selection or self._keyboard_extend_selection
            toggle = toggle or self._pointer_toggle_selection

        if normalized is None:
            new_indices: set[int] = set()
            primary = None
            anchor = None
        elif extend:
            anchor = self._selection_anchor
            if anchor is None:
                anchor = self._selected_index if self._selected_index is not None else normalized
            start, stop = sorted((anchor, normalized))
            new_indices = set(range(start, stop + 1))
            primary = normalized
        elif toggle:
            new_indices = set(self._selected_indices)
            if normalized in new_indices:
                new_indices.remove(normalized)
                primary = self._nearest_selected_index(normalized, new_indices)
            else:
                new_indices.add(normalized)
                primary = normalized
            anchor = normalized
        else:
            new_indices = {normalized}
            primary = normalized
            anchor = normalized

        return self._apply_selection(
            new_indices,
            primary_index=primary,
            anchor_index=anchor,
            ensure_visible=ensure_visible,
        )

    def select_rows(
        self,
        indices: Sequence[int],
        *,
        primary_index: int | None = None,
        ensure_visible: bool = True,
    ) -> DataGrid:
        """Replace selection with explicit row indices."""

        normalized = tuple(
            dict.fromkeys(self._normalize_required_index(index) for index in indices)
        )
        if self._selection_mode == "single" and len(normalized) > 1:
            raise ValueError("DataGrid single selection mode accepts at most one row.")
        if not normalized:
            return self.select_row(None, ensure_visible=ensure_visible)

        primary = (
            normalized[0]
            if primary_index is None
            else self._normalize_required_index(primary_index)
        )
        if primary not in normalized:
            raise ValueError("primary_index must be part of the selected indices.")
        return self._apply_selection(
            set(normalized),
            primary_index=primary,
            anchor_index=primary,
            ensure_visible=ensure_visible,
        )

    def select_all(self, *, ensure_visible: bool = False) -> DataGrid:
        """Select every row in multiple mode."""

        if self._selection_mode != "multiple":
            raise ValueError("DataGrid select_all requires selection_mode='multiple'.")
        if not self.rows:
            return self.select_row(None, ensure_visible=ensure_visible)
        primary = self._selected_index if self._selected_index is not None else 0
        return self._apply_selection(
            set(range(len(self.rows))),
            primary_index=primary,
            anchor_index=primary,
            ensure_visible=ensure_visible,
        )

    def clear_selection(self) -> DataGrid:
        """Clear all selected rows."""

        return self.select_row(None, ensure_visible=False)

    def set_rows(self, rows: Sequence[Mapping[str, object]]) -> DataGrid:
        """Replace rows while preserving every still-present selected snapshot."""

        selected = self.selected_rows
        primary = self.selected_row
        anchor = self._row_at_index(self._selection_anchor)
        super().set_rows(rows)
        self._restore_selection(selected, primary=primary, anchor=anchor)
        return self

    def sort_by(self, column_key: str | None, *, descending: bool = False) -> DataGrid:
        """Sort while preserving the complete multi-selection by row snapshot."""

        selected = self.selected_rows
        primary = self.selected_row
        anchor = self._row_at_index(self._selection_anchor)
        super().sort_by(column_key, descending=descending)
        self._restore_selection(selected, primary=primary, anchor=anchor)
        return self

    def build_scene_node(self) -> SceneNode:
        """Compile the base virtualized scene and paint all selected visible rows."""

        root = super().build_scene_node()
        prefix = f"{self.key}:row:"
        for child in root.children:
            if not child.key.startswith(prefix):
                continue
            suffix = child.key.removeprefix(prefix)
            if suffix.isdigit() and int(suffix) in self._selected_indices:
                child.fill = self._selected_background
        return root

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        use_modifiers = (
            self._selection_mode == "multiple"
            and platform_event is not None
            and platform_event.button is PointerButton.LEFT
            and platform_event.y is not None
            and platform_event.y >= self.bounds.y + self._header_height
        )
        if use_modifiers:
            self._pointer_extend_selection = bool(platform_event.shift)
            self._pointer_toggle_selection = bool(
                (platform_event.ctrl or platform_event.meta) and not platform_event.shift
            )
        try:
            super()._on_pointer_down(event)
        finally:
            self._pointer_extend_selection = False
            self._pointer_toggle_selection = False

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if (
            self._selection_mode == "multiple"
            and self.enabled
            and platform_event is not None
            and not platform_event.alt
            and not platform_event.meta
            and platform_event.ctrl
            and platform_event.key_code == _VK_A
        ):
            self.select_all(ensure_visible=False)
            event.prevent_default()
            return
        if (
            self._selection_mode == "multiple"
            and self.enabled
            and platform_event is not None
            and not platform_event.alt
            and not platform_event.meta
            and platform_event.ctrl
            and platform_event.key_code == _VK_SPACE
            and self._selected_index is not None
        ):
            self.select_row(self._selected_index, toggle=True, ensure_visible=True)
            event.prevent_default()
            return

        self._keyboard_extend_selection = bool(
            self._selection_mode == "multiple"
            and platform_event is not None
            and platform_event.shift
            and not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
            and platform_event.key_code in _ROW_NAVIGATION_KEYS
        )
        try:
            super()._on_key_down(event)
        finally:
            self._keyboard_extend_selection = False

    def _apply_selection(
        self,
        indices: set[int],
        *,
        primary_index: int | None,
        anchor_index: int | None,
        ensure_visible: bool,
    ) -> DataGrid:
        if primary_index is not None and primary_index not in indices:
            raise ValueError("DataGrid primary selection must be selected.")
        previous_indices = self._selected_indices
        previous_primary = self._selected_index
        changed = indices != previous_indices or primary_index != previous_primary

        self._selected_indices = set(indices)
        self._selected_index = primary_index
        self._selection_anchor = anchor_index
        if primary_index is not None and ensure_visible:
            self.scroll_to_row(primary_index)
        self._sync_accessible_selection()

        if not changed:
            return self
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=primary_index,
            row=None if primary_index is None else self.rows[primary_index],
            indices=self.selected_indices,
            rows=self.selected_rows,
        )
        return self

    def _restore_selection(
        self,
        selected: Sequence[Mapping[str, object]],
        *,
        primary: Mapping[str, object] | None,
        anchor: Mapping[str, object] | None,
    ) -> None:
        mapped = self._matching_row_indices(selected)
        primary_index = self._matching_row_index(primary, allowed=mapped)
        if primary_index is None and mapped:
            primary_index = min(mapped)
        anchor_index = self._matching_row_index(anchor, allowed=mapped)
        if anchor_index is None:
            anchor_index = primary_index
        self._selected_indices = mapped
        self._selected_index = primary_index
        self._selection_anchor = anchor_index
        self._sync_accessible_selection()

    def _matching_row_indices(
        self,
        snapshots: Sequence[Mapping[str, object]],
    ) -> set[int]:
        mapped: set[int] = set()
        for snapshot in snapshots:
            index = self._matching_row_index(snapshot, excluded=mapped)
            if index is not None:
                mapped.add(index)
        return mapped

    def _matching_row_index(
        self,
        snapshot: Mapping[str, object] | None,
        *,
        allowed: set[int] | None = None,
        excluded: set[int] | None = None,
    ) -> int | None:
        if snapshot is None:
            return None
        candidates = range(len(self.rows)) if allowed is None else sorted(allowed)
        for index in candidates:
            if excluded is not None and index in excluded:
                continue
            if self.rows[index] is snapshot:
                return index
        for index in candidates:
            if excluded is not None and index in excluded:
                continue
            if self.rows[index] == snapshot:
                return index
        return None

    def _row_at_index(self, index: int | None) -> Mapping[str, object] | None:
        if index is None or not 0 <= index < len(self.rows):
            return None
        return self.rows[index]

    def _normalize_selection_index(self, index: int | None) -> int | None:
        if index is None:
            return None
        return self._normalize_required_index(index)

    def _normalize_required_index(self, index: int) -> int:
        normalized = int(index)
        if not 0 <= normalized < len(self.rows):
            raise IndexError("DataGrid row index is out of range.")
        return normalized

    @staticmethod
    def _nearest_selected_index(origin: int, selected: set[int]) -> int | None:
        if not selected:
            return None
        return min(selected, key=lambda index: (abs(index - origin), index))

    def _sync_accessible_selection(self) -> None:
        count = len(self._selected_indices)
        noun = "row" if count == 1 else "rows"
        self.accessible_value_text = f"{count} {noun} selected of {len(self.rows)}"
