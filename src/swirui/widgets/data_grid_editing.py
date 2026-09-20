"""In-place cell editing layered on the professional virtualized DataGrid."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from swirui.core import Event
from swirui.platforms import PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .data_grid import DataGridColumn
from .data_grid_accessibility import DataGrid as _DataGrid
from .data_grid_selection import DataGridSelectionMode

_VK_BACK = 0x08
_VK_TAB = 0x09
_VK_RETURN = 0x0D
_VK_ESCAPE = 0x1B
_VK_HOME = 0x24
_VK_END = 0x23
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_DELETE = 0x2E
_VK_F2 = 0x71

_EDIT_NAVIGATION_KEYS = frozenset(
    {_VK_HOME, _VK_END, _VK_PRIOR, _VK_NEXT, _VK_LEFT, _VK_UP, _VK_RIGHT, _VK_DOWN}
)
_UNSET = object()

CellEditParser = Callable[[str, object], object]


class DataGrid(_DataGrid):
    """Professional DataGrid with opt-in retained in-place cell editing.

    Editing is intentionally opt-in per column. The grid keeps its public row
    snapshots immutable from the caller's point of view, commits edited values
    into a new retained source-row snapshot, preserves selection across active
    sorting, and repositions the edited row when a sort key changes.

    Keyboard editing starts with F2 or Enter on an active editable cell. Routed
    ``text_input`` appends Unicode text; Backspace/Delete edit the buffer,
    Enter commits, Escape cancels, and Tab commits before normal focus traversal.
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
    ) -> None:
        self._editing_row_index: int | None = None
        self._editing_source_index: int | None = None
        self._editing_column_key: str | None = None
        self._editing_original_value: object = None
        self._editing_text = ""
        self._cell_edit_parser = cell_edit_parser

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

        normalized_editable = frozenset(
            key.strip() for key in (str(value) for value in editable_columns) if key.strip()
        )
        known_columns = {column.key for column in self.columns}
        unknown = sorted(normalized_editable.difference(known_columns))
        if unknown:
            joined = ", ".join(repr(key) for key in unknown)
            raise KeyError(f"Unknown editable DataGrid column(s): {joined}")
        self._editable_column_keys = normalized_editable
        self.on("text_input", self._on_text_input)
        self.on("focus_lost", self._on_focus_lost)

    @property
    def editable_column_keys(self) -> tuple[str, ...]:
        """Return editable columns in the current visual column order."""

        return tuple(
            column.key for column in self.columns if column.key in self._editable_column_keys
        )

    @property
    def is_editing(self) -> bool:
        """Return whether one retained cell currently owns the edit buffer."""

        return self._editing_row_index is not None and self._editing_column_key is not None

    @property
    def editing_cell(self) -> tuple[int, str, str] | None:
        """Return ``(row_index, column_key, text_buffer)`` for the active edit."""

        if self._editing_row_index is None or self._editing_column_key is None:
            return None
        return self._editing_row_index, self._editing_column_key, self._editing_text

    def begin_edit(
        self,
        row_index: int | None = None,
        column_key: str | None = None,
        *,
        ensure_visible: bool = True,
    ) -> DataGrid:
        """Start editing one opt-in cell and seed the buffer from its value."""

        if not self.enabled:
            raise RuntimeError("Cannot edit a disabled DataGrid.")
        if not self.rows:
            raise RuntimeError("Cannot edit an empty DataGrid.")

        resolved_row = self.selected_index if row_index is None else int(row_index)
        if resolved_row is None:
            resolved_row = 0
        if not 0 <= resolved_row < len(self.rows):
            raise IndexError("DataGrid row index is out of range.")

        resolved_column = column_key
        if resolved_column is None:
            resolved_column = self.active_column_key
        if resolved_column is None:
            resolved_column = next(iter(self.editable_column_keys), None)
        if resolved_column is None:
            raise RuntimeError("DataGrid has no editable columns.")

        column = self._column_by_key(resolved_column)
        if column.key not in self._editable_column_keys:
            raise ValueError(f"DataGrid column {column.key!r} is not editable.")

        if (
            self._editing_row_index == resolved_row
            and self._editing_column_key == column.key
        ):
            if ensure_visible:
                self.scroll_to_row(resolved_row)
                self.scroll_to_column(column.key)
            return self

        if self.is_editing:
            self.cancel_edit(reason="replaced")

        row = self.rows[resolved_row]
        source_index = self._source_index_for_row(row)
        if resolved_row in self._selected_indices:
            anchor = self._selection_anchor
            self._apply_selection(
                set(self._selected_indices),
                primary_index=resolved_row,
                anchor_index=resolved_row if anchor is None else anchor,
                ensure_visible=ensure_visible,
            )
        else:
            self.select_row(resolved_row, ensure_visible=ensure_visible)
        self._set_active_column(column.key, ensure_visible=ensure_visible)
        value = row.get(column.key)

        self._editing_row_index = self.selected_index
        self._editing_source_index = source_index
        self._editing_column_key = column.key
        self._editing_original_value = value
        self._editing_text = "" if value is None else str(value)
        self.invalidate(reason="cell_edit_started")
        self.emit(
            "cell_edit_started",
            row_index=self._editing_row_index,
            source_index=source_index,
            column_key=column.key,
            value=value,
            text=self._editing_text,
        )
        return self

    def set_edit_text(self, value: str) -> DataGrid:
        """Replace the current Unicode edit buffer without committing it."""

        if not self.is_editing:
            raise RuntimeError("DataGrid is not editing a cell.")
        normalized = str(value)
        if normalized == self._editing_text:
            return self
        self._editing_text = normalized
        self.invalidate(reason="cell_edit_text")
        self.emit(
            "cell_edit_changed",
            row_index=self._editing_row_index,
            column_key=self._editing_column_key,
            text=self._editing_text,
        )
        return self

    def commit_edit(self, value: object = _UNSET) -> DataGrid:
        """Commit the active edit into a new retained source-row snapshot."""

        if (
            self._editing_row_index is None
            or self._editing_source_index is None
            or self._editing_column_key is None
        ):
            raise RuntimeError("DataGrid is not editing a cell.")

        source_index = self._editing_source_index
        column_key = self._editing_column_key
        old_value = self._editing_original_value
        if value is _UNSET:
            parser = self._cell_edit_parser
            new_value = (
                self._editing_text
                if parser is None
                else parser(self._editing_text, old_value)
            )
        else:
            new_value = value

        selected_source_indices = tuple(
            self._source_index_for_row(self.rows[index]) for index in self.selected_indices
        )
        primary_source_index = (
            None
            if self.selected_index is None
            else self._source_index_for_row(self.rows[self.selected_index])
        )
        anchor_row = self._row_at_index(self._selection_anchor)
        anchor_source_index = (
            None if anchor_row is None else self._source_index_for_row(anchor_row)
        )

        source_rows = list(self._source_rows)
        updated_row = dict(source_rows[source_index])
        updated_row[column_key] = new_value
        source_rows[source_index] = updated_row
        self._source_rows = tuple(source_rows)
        self._rows = self._apply_sort(self._source_rows)

        selected_rows = tuple(
            self._source_rows[index] for index in selected_source_indices
        )
        primary_row = (
            None
            if primary_source_index is None
            else self._source_rows[primary_source_index]
        )
        anchor_row_after = (
            None
            if anchor_source_index is None
            else self._source_rows[anchor_source_index]
        )
        self._restore_selection(
            selected_rows,
            primary=primary_row,
            anchor=anchor_row_after,
        )

        new_row_index = self._find_matching_row(self._rows, updated_row)
        self._clear_edit_state()
        if new_row_index is not None and primary_source_index == source_index:
            self.scroll_to_row(new_row_index)
        self.invalidate(reason="cell_edit_committed")
        self.emit(
            "cell_edit_committed",
            row_index=new_row_index,
            source_index=source_index,
            column_key=column_key,
            old_value=old_value,
            value=new_value,
            changed=new_value != old_value,
        )
        return self

    def cancel_edit(self, *, reason: str = "cancelled") -> DataGrid:
        """Discard the active edit buffer without changing retained rows."""

        if not self.is_editing:
            return self
        row_index = self._editing_row_index
        source_index = self._editing_source_index
        column_key = self._editing_column_key
        original = self._editing_original_value
        text = self._editing_text
        self._clear_edit_state()
        self.invalidate(reason="cell_edit_cancelled")
        self.emit(
            "cell_edit_cancelled",
            row_index=row_index,
            source_index=source_index,
            column_key=column_key,
            value=original,
            text=text,
            reason=reason,
        )
        return self

    def set_rows(self, rows: Sequence[Mapping[str, object]]) -> DataGrid:
        """Replace rows, cancelling a stale edit before source identity changes."""

        if self.is_editing:
            self.cancel_edit(reason="rows_replaced")
        super().set_rows(rows)
        return self

    def sort_by(self, column_key: str | None, *, descending: bool = False) -> DataGrid:
        """Sort rows, cancelling a stale edit before visual row indices move."""

        if self.is_editing:
            self.cancel_edit(reason="sort_changed")
        super().sort_by(column_key, descending=descending)
        return self

    def build_scene_node(self) -> SceneNode:
        """Compile the virtualized grid plus a retained visible edit overlay."""

        root = super().build_scene_node()
        editor = self._editing_cell_bounds()
        if editor is None:
            return root

        bounds = editor
        root.add(
            SceneNode(
                key=f"{self.key}:editor:background",
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                fill=self._header_background,
                z_index=6,
                clip_to_bounds=True,
                hit_testable=False,
            )
        )
        text = self._text_node(
            key=f"{self.key}:editor:text",
            bounds=bounds,
            text=f"{self._editing_text}│",
            color=self._header_foreground,
            font_size=self._font_size,
        )
        text.z_index = 7
        root.add(text)
        return root

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            self.is_editing
            and platform_event is not None
            and platform_event.button is PointerButton.LEFT
            and platform_event.x is not None
            and platform_event.y is not None
            and not self._point_hits_editing_cell(platform_event.x, platform_event.y)
        ):
            self.cancel_edit(reason="pointer_navigation")
        super()._on_pointer_down(event)

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or platform_event.key_code is None:
            return

        key = platform_event.key_code
        if self.is_editing:
            if platform_event.ctrl or platform_event.alt or platform_event.meta:
                return
            if key == _VK_RETURN:
                self.commit_edit()
                event.prevent_default()
            elif key == _VK_ESCAPE:
                self.cancel_edit(reason="escape")
                event.prevent_default()
            elif key == _VK_BACK:
                self.set_edit_text(self._editing_text[:-1])
                event.prevent_default()
            elif key == _VK_DELETE:
                self.set_edit_text("")
                event.prevent_default()
            elif key == _VK_TAB:
                self.commit_edit()
            elif key == _VK_F2 or key in _EDIT_NAVIGATION_KEYS:
                event.prevent_default()
            return

        if (
            not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
            and key in {_VK_F2, _VK_RETURN}
        ):
            target = self._editable_target()
            if target is not None:
                self.begin_edit(*target, ensure_visible=True)
                event.prevent_default()
                return

        super()._on_key_down(event)

    def _on_text_input(self, event: Event) -> None:
        if not self.enabled or not self.is_editing:
            return
        platform_event = self._platform_event(event, PlatformEventKind.TEXT_INPUT)
        if platform_event is None or platform_event.text is None:
            return
        text = platform_event.text.replace("\r", "").replace("\n", "")
        if not text:
            return
        self.set_edit_text(f"{self._editing_text}{text}")
        event.prevent_default()

    def _on_focus_lost(self, _event: Event) -> None:
        if self.is_editing:
            self.cancel_edit(reason="focus_lost")

    def _editable_target(self) -> tuple[int, str] | None:
        if not self.rows:
            return None
        row_index = self.selected_index
        if row_index is None:
            return None
        column_key = self.active_column_key
        if column_key in self._editable_column_keys:
            return row_index, column_key
        for candidate in self.editable_column_keys:
            return row_index, candidate
        return None

    def _editing_cell_bounds(self) -> Rect | None:
        row_index = self._editing_row_index
        column_key = self._editing_column_key
        if row_index is None or column_key is None or row_index not in self.visible_row_range:
            return None
        visible = next(
            (
                (x, width)
                for column, x, width in self._visible_columns()
                if column.key == column_key
            ),
            None,
        )
        if visible is None:
            return None
        x, width = visible
        body_top = self.bounds.y + self._header_height
        y = body_top + (row_index * self._row_height) - self._effective_scroll_offset()
        return Rect(x, y, width, self._row_height)

    def _point_hits_editing_cell(self, x: float, y: float) -> bool:
        bounds = self._editing_cell_bounds()
        if bounds is None:
            return False
        return bounds.x <= x < bounds.right and bounds.y <= y < bounds.bottom

    def _source_index_for_row(self, row: Mapping[str, object]) -> int:
        for index, source_row in enumerate(self._source_rows):
            if source_row is row:
                return index
        for index, source_row in enumerate(self._source_rows):
            if source_row == row:
                return index
        raise RuntimeError("DataGrid row is no longer present in the retained source snapshot.")

    def _clear_edit_state(self) -> None:
        self._editing_row_index = None
        self._editing_source_index = None
        self._editing_column_key = None
        self._editing_original_value = None
        self._editing_text = ""
