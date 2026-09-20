"""Retained row filtering layered on the professional DataGrid."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from swirui.rendering.geometry import Color, Rect

from .data_grid import DataGridColumn
from .data_grid_editing import CellEditParser
from .data_grid_editing import DataGrid as _DataGrid
from .data_grid_selection import DataGridSelectionMode

RowFilter = Callable[[Mapping[str, object]], bool]


class DataGrid(_DataGrid):
    """Professional DataGrid with source-preserving retained row filtering.

    Filtering never mutates or replaces the source-row snapshot. It composes
    with stable sorting, virtualization, multi-selection and in-place editing:
    visible rows are filtered first and then sorted, while selection is kept
    only for rows that remain visible. Editing a row may therefore naturally
    remove it from the viewport when the committed value no longer matches the
    active predicate.
    """

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
        editable_columns: Sequence[str] = (),
        cell_edit_parser: CellEditParser | None = None,
        row_filter: RowFilter | None = None,
    ) -> None:
        self._row_filter = row_filter
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
            selection_mode=selection_mode,
            editable_columns=editable_columns,
            cell_edit_parser=cell_edit_parser,
        )
        if row_filter is not None:
            self._rows = self._apply_sort(self._source_rows)
            self._scroll_offset = min(self._scroll_offset, self._max_scroll_offset())
            self._sync_accessible_selection()

    @property
    def row_filter(self) -> RowFilter | None:
        """Return the currently active row predicate, if any."""

        return self._row_filter

    @property
    def is_filtered(self) -> bool:
        """Return whether a retained row filter is active."""

        return self._row_filter is not None

    @property
    def source_row_count(self) -> int:
        """Return the unfiltered retained source-row count."""

        return len(self._source_rows)

    def set_filter(self, predicate: RowFilter | None) -> DataGrid:
        """Apply a row predicate while preserving visible selection and sort."""

        if predicate is self._row_filter:
            return self
        if self.is_editing:
            self.cancel_edit(reason="filter_changed")

        selected = self.selected_rows
        primary = self.selected_row
        anchor = self._row_at_index(self._selection_anchor)
        self._row_filter = predicate
        self._rows = self._apply_sort(self._source_rows)
        self._restore_selection(selected, primary=primary, anchor=anchor)
        self._scroll_offset = min(self._scroll_offset, self._max_scroll_offset())
        self._sync_accessible_selection()
        self.invalidate(reason="row_filter")
        self.emit(
            "filter_changed",
            active=predicate is not None,
            visible_count=len(self._rows),
            source_count=len(self._source_rows),
        )
        return self

    def clear_filter(self) -> DataGrid:
        """Restore every retained source row without changing active sorting."""

        return self.set_filter(None)

    def _apply_sort(
        self,
        rows: tuple[Mapping[str, object], ...],
    ) -> tuple[Mapping[str, object], ...]:
        predicate = self._row_filter
        visible = rows if predicate is None else tuple(row for row in rows if predicate(row))
        return super()._apply_sort(visible)
