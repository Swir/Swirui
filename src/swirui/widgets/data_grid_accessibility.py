"""Table/row/cell accessibility semantics for the virtualized DataGrid."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from swirui.core import AccessibilityNode, AccessibilityRole, Component
from swirui.rendering.geometry import Color, Rect

from .data_grid import DataGridColumn
from .data_grid_selection import DataGrid as _DataGrid
from .data_grid_selection import DataGridSelectionMode


class DataGrid(_DataGrid):
    """Professional DataGrid with virtualized table accessibility semantics."""

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
        )
        self.accessibility_role = AccessibilityRole.TABLE

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        """Expose logical table dimensions plus only the currently virtualized rows/cells."""

        visible_keys = set(self.visible_column_keys)
        visible_columns = tuple(
            (column_index, column)
            for column_index, column in enumerate(self.columns)
            if column.key in visible_keys
        )
        headers = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:header:{column.key}",
                role=AccessibilityRole.COLUMN_HEADER,
                name=column.header,
                description=None,
                enabled=self.enabled,
                focusable=False,
                focused=False,
                column_index=column_index,
            )
            for column_index, column in visible_columns
        )

        selected_indices = set(self.selected_indices)
        table_focused = focused is self
        rows = tuple(
            self._accessibility_row(
                row_index,
                visible_columns=visible_columns,
                selected=row_index in selected_indices,
                table_focused=table_focused,
            )
            for row_index in self.visible_row_range
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.TABLE,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=table_focused,
            value_text=self.accessible_value_text,
            children=headers + rows,
            row_count=len(self.rows),
            column_count=len(self.columns),
        )

    def _accessibility_row(
        self,
        row_index: int,
        *,
        visible_columns: tuple[tuple[int, DataGridColumn], ...],
        selected: bool,
        table_focused: bool,
    ) -> AccessibilityNode:
        row = self.rows[row_index]
        cells = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:cell:{row_index}:{column.key}",
                role=AccessibilityRole.CELL,
                name=self._cell_accessible_name(column, row.get(column.key)),
                description=None,
                enabled=self.enabled,
                focusable=False,
                focused=False,
                selected=selected,
                active=bool(
                    table_focused
                    and row_index == self.selected_index
                    and column.key == self.active_column_key
                ),
                row_index=row_index,
                column_index=column_index,
            )
            for column_index, column in visible_columns
        )
        return AccessibilityNode(
            key=f"{self.key}:a11y:row:{row_index}",
            role=AccessibilityRole.ROW,
            name=f"Row {row_index + 1}",
            description=None,
            enabled=self.enabled,
            focusable=False,
            focused=False,
            children=cells,
            selected=selected,
            active=bool(table_focused and row_index == self.selected_index),
            row_index=row_index,
            column_count=len(self.columns),
        )

    @staticmethod
    def _cell_accessible_name(column: DataGridColumn, value: object) -> str:
        rendered = "" if value is None else str(value)
        return column.header if not rendered else f"{column.header}: {rendered}"
