"""Cell-aware keyboard navigation layered on the professional DataGrid."""

from __future__ import annotations

from swirui.core import Event
from swirui.platforms import PlatformEventKind, PointerButton

from .data_grid_drag import DataGrid as _DataGrid

_VK_HOME = 0x24
_VK_END = 0x23
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_ROW_NAVIGATION_KEYS = frozenset({_VK_HOME, _VK_END, _VK_PRIOR, _VK_NEXT, _VK_UP, _VK_DOWN})


class DataGrid(_DataGrid):
    """DataGrid with an explicit active cell and two-axis keyboard navigation.

    Row selection remains the public selection model. The active column adds a
    stable cell cursor on top of that model so professional table workflows can
    move horizontally without replacing or copying row data.
    """

    _active_column_key: str | None = None

    @property
    def active_column_key(self) -> str | None:
        """Return the active cell column, if a cell cursor has been established."""

        return self._active_column_key

    @property
    def active_cell(self) -> tuple[int, str, object] | None:
        """Return ``(row_index, column_key, value)`` for the active cell."""

        row_index = self.selected_index
        column_key = self._active_column_key
        if row_index is None or column_key is None:
            return None
        return row_index, column_key, self.rows[row_index].get(column_key)

    def activate_cell(
        self,
        row_index: int,
        column_key: str,
        *,
        ensure_visible: bool = True,
    ) -> DataGrid:
        """Move the retained cell cursor and optionally reveal both axes."""

        column = self._column_by_key(column_key)
        self.select_row(row_index, ensure_visible=ensure_visible)
        self._set_active_column(column.key, ensure_visible=ensure_visible)
        return self

    def scroll_to_column(self, column_key: str) -> DataGrid:
        """Ensure one whole column is visible when its width permits it."""

        index = self._column_index(column_key)
        column_left = sum(column.resolved_width for column in self.columns[:index])
        column_width = self.columns[index].resolved_width
        column_right = column_left + column_width
        viewport_width = self.bounds.width
        if viewport_width <= 0.0:
            return self

        offset = self._effective_horizontal_scroll_offset()
        if column_width >= viewport_width:
            target = column_left
        elif column_left < offset:
            target = column_left
        elif column_right > offset + viewport_width:
            target = column_right - viewport_width
        else:
            return self
        return self._set_horizontal_scroll_offset(target)

    def _set_active_column(self, column_key: str, *, ensure_visible: bool) -> None:
        normalized = self._column_by_key(column_key).key
        if normalized == self._active_column_key:
            if ensure_visible:
                self.scroll_to_column(normalized)
            return

        self._active_column_key = normalized
        if ensure_visible:
            self.scroll_to_column(normalized)
        self.invalidate(reason="active_cell")
        row_index = self.selected_index
        self.emit(
            "active_column_changed",
            row_index=row_index,
            column_key=normalized,
            value=None if row_index is None else self.rows[row_index].get(normalized),
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        body_column_key: str | None = None
        if (
            self.enabled
            and platform_event is not None
            and platform_event.button is PointerButton.LEFT
            and platform_event.x is not None
            and platform_event.y is not None
            and self._contains_point(platform_event.x, platform_event.y)
            and platform_event.y >= self.bounds.y + self._header_height
        ):
            column = self._column_at_x(platform_event.x)
            body_column_key = None if column is None else column.key

        super()._on_pointer_down(event)

        if body_column_key is not None and self.selected_index is not None:
            self._set_active_column(body_column_key, ensure_visible=False)

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if (
            self.enabled
            and platform_event is not None
            and not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
            and platform_event.key_code in (_VK_LEFT, _VK_RIGHT)
        ):
            if not self.rows:
                return
            if self.selected_index is None:
                self.select_row(0, ensure_visible=True)

            current_key = self._active_column_key
            if current_key is None:
                target_index = 0
            else:
                current_index = self._column_index(current_key)
                direction = -1 if platform_event.key_code == _VK_LEFT else 1
                target_index = min(len(self.columns) - 1, max(0, current_index + direction))
            self._set_active_column(
                self.columns[target_index].key,
                ensure_visible=True,
            )
            event.prevent_default()
            return

        super()._on_key_down(event)

        if (
            platform_event is not None
            and platform_event.key_code in _ROW_NAVIGATION_KEYS
            and not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
            and self.selected_index is not None
            and self._active_column_key is None
        ):
            self._set_active_column(self.columns[0].key, ensure_visible=True)
