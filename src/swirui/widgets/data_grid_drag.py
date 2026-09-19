"""Direct header-drag interactions layered on the retained DataGrid."""

from __future__ import annotations

from swirui.core import Event
from swirui.platforms import PlatformEventKind, PointerButton

from .data_grid import DataGrid as _RetainedDataGrid

_HEADER_DRAG_THRESHOLD = 6.0
_HEADER_DRAG_EDGE_ZONE = 28.0
_HEADER_DRAG_SCROLL_STEP = 36.0


class DataGrid(_RetainedDataGrid):
    """Professional DataGrid with direct, retained header drag reordering.

    The base grid keeps separator resize and programmatic column ordering
    semantics. This interaction layer adds direct pointer dragging with a
    movement threshold, exact retained column moves and horizontal edge
    auto-scroll. Header sorting is committed only on pointer-up so a drag never
    causes a transient row reorder or a misleading ``sort_changed`` event.
    """

    _header_press_key: str | None = None
    _header_press_x = 0.0
    _header_press_index = 0
    _header_drag_started = False

    @property
    def dragging_column_key(self) -> str | None:
        """Return the column currently being directly reordered, if any."""

        return self._header_press_key if self._header_drag_started else None

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            self.enabled
            and platform_event is not None
            and platform_event.button is PointerButton.LEFT
            and platform_event.x is not None
            and platform_event.y is not None
            and self._contains_point(platform_event.x, platform_event.y)
            and platform_event.y < self.bounds.y + self._header_height
        ):
            resize_key = self._separator_hit(platform_event.x)
            if resize_key is not None and self._column_by_key(resize_key).resizable:
                self._clear_header_press()
                super()._on_pointer_down(event)
                return

            header_column = self._column_at_x(platform_event.x)
            if header_column is not None:
                self._header_press_key = header_column.key
                self._header_press_x = platform_event.x
                self._header_press_index = self._column_index(header_column.key)
                self._header_drag_started = False
                # Defer click-to-sort until pointer-up. This keeps the row model
                # stable while the gesture is still ambiguous between click and
                # drag, and avoids firing a sort event that immediately needs to
                # be undone when the movement threshold is crossed.
                event.prevent_default()
                return

        self._clear_header_press()
        super()._on_pointer_down(event)

    def _on_pointer_move(self, event: Event) -> None:
        if self._resizing_column_key is not None:
            super()._on_pointer_move(event)
            return

        column_key = self._header_press_key
        if column_key is None:
            super()._on_pointer_move(event)
            return

        platform_event = self._platform_event(event, PlatformEventKind.POINTER_MOVE)
        if platform_event is None or platform_event.x is None:
            return

        if not self._header_drag_started:
            if abs(platform_event.x - self._header_press_x) < _HEADER_DRAG_THRESHOLD:
                return
            self._header_drag_started = True
            self.emit(
                "column_drag_started",
                column_key=column_key,
                old_index=self._header_press_index,
            )

        self._auto_scroll_for_header_drag(platform_event.x)
        target_index = self._drag_target_index(platform_event.x)
        if target_index != self._column_index(column_key):
            self.move_column(column_key, target_index)
        event.prevent_default()

    def _on_pointer_up(self, event: Event) -> None:
        if self._resizing_column_key is not None:
            super()._on_pointer_up(event)
            return

        column_key = self._header_press_key
        if column_key is None:
            super()._on_pointer_up(event)
            return

        platform_event = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if platform_event is None:
            return

        dragged = self._header_drag_started
        old_index = self._header_press_index
        new_index = self._column_index(column_key)
        self._clear_header_press()
        if dragged:
            self.emit(
                "column_drag_finished",
                column_key=column_key,
                old_index=old_index,
                new_index=new_index,
            )
            event.prevent_default()
            return

        column = self._column_by_key(column_key)
        if column.sortable:
            self.toggle_sort(column_key)
        event.prevent_default()

    def _auto_scroll_for_header_drag(self, x: float) -> None:
        if self.content_width <= self.bounds.width:
            return
        left = self.bounds.x
        right = self.bounds.x + self.bounds.width
        if x <= left + _HEADER_DRAG_EDGE_ZONE:
            self.scroll_horizontal_by(-_HEADER_DRAG_SCROLL_STEP)
        elif x >= right - _HEADER_DRAG_EDGE_ZONE:
            self.scroll_horizontal_by(_HEADER_DRAG_SCROLL_STEP)

    def _drag_target_index(self, x: float) -> int:
        if x <= self.bounds.x:
            return 0
        if x >= self.bounds.x + self.bounds.width:
            return len(self.columns) - 1
        column = self._column_at_x(x)
        return len(self.columns) - 1 if column is None else self._column_index(column.key)

    def _clear_header_press(self) -> None:
        self._header_press_key = None
        self._header_press_x = 0.0
        self._header_press_index = 0
        self._header_drag_started = False
