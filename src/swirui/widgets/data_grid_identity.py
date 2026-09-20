"""Stable row identity layered on the professional retained DataGrid."""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence

from swirui.rendering.geometry import Color, Rect

from .data_grid import DataGridColumn
from .data_grid_editing import CellEditParser
from .data_grid_filtering import DataGrid as _DataGrid
from .data_grid_filtering import RowFilter
from .data_grid_selection import DataGridSelectionMode


class DataGrid(_DataGrid):
    """Professional DataGrid with an optional stable retained row identity.

    ``row_key`` names a mapping field whose value uniquely identifies a source
    row. When configured, selection survives immutable row replacement even if
    other cell values changed, and edit/source lookup no longer depends on full
    mapping equality. Identity values must be present, hashable and unique.
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
        row_key: str | None = None,
    ) -> None:
        normalized_row_key = None if row_key is None else str(row_key).strip()
        if row_key is not None and not normalized_row_key:
            raise ValueError("DataGrid row_key must not be empty.")
        normalized_editable = {
            str(column_key).strip() for column_key in editable_columns if str(column_key).strip()
        }
        if normalized_row_key is not None and normalized_row_key in normalized_editable:
            raise ValueError("DataGrid row_key cannot also be an editable column.")

        self._row_key = normalized_row_key
        self._validate_row_identities(rows)
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
            row_filter=row_filter,
        )

    @property
    def row_key(self) -> str | None:
        """Return the configured stable source-row identity field."""

        return self._row_key

    def set_rows(self, rows: Sequence[Mapping[str, object]]) -> DataGrid:
        """Replace source rows only after validating the stable identity contract."""

        self._validate_row_identities(rows)
        super().set_rows(rows)
        return self

    def _matching_row_index(
        self,
        snapshot: Mapping[str, object] | None,
        *,
        allowed: set[int] | None = None,
        excluded: set[int] | None = None,
    ) -> int | None:
        row_key = self._row_key
        if row_key is None:
            return super()._matching_row_index(
                snapshot,
                allowed=allowed,
                excluded=excluded,
            )
        if snapshot is None or row_key not in snapshot:
            return None

        identity = snapshot[row_key]
        candidates = range(len(self.rows)) if allowed is None else sorted(allowed)
        for index in candidates:
            if excluded is not None and index in excluded:
                continue
            if self.rows[index].get(row_key) == identity:
                return index
        return None

    def _source_index_for_row(self, row: Mapping[str, object]) -> int:
        row_key = self._row_key
        if row_key is None:
            return super()._source_index_for_row(row)
        if row_key not in row:
            raise RuntimeError("DataGrid row does not contain the configured row_key.")

        identity = row[row_key]
        for index, source_row in enumerate(self._source_rows):
            if source_row.get(row_key) == identity:
                return index
        raise RuntimeError("DataGrid row identity is no longer present in the source snapshot.")

    def _validate_row_identities(self, rows: Sequence[Mapping[str, object]]) -> None:
        row_key = self._row_key
        if row_key is None:
            return

        seen: set[Hashable] = set()
        for index, row in enumerate(rows):
            if row_key not in row:
                raise KeyError(
                    f"DataGrid row {index} is missing configured row_key {row_key!r}."
                )
            identity = row[row_key]
            if not isinstance(identity, Hashable):
                raise TypeError(
                    f"DataGrid row_key value at row {index} must be hashable."
                )
            if identity in seen:
                raise ValueError(
                    f"DataGrid row_key {row_key!r} must contain unique values; "
                    f"duplicate {identity!r} at row {index}."
                )
            seen.add(identity)
