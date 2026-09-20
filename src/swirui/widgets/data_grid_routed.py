"""Component-routed wheel/trackpad input for the professional DataGrid."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from swirui.core import Event

from .data_grid_keyboard import DataGrid as _DataGrid
from .scroll_events import routed_scroll_deltas, update_scroll_residual

if TYPE_CHECKING:
    from swirui.window import Window


class DataGrid(_DataGrid):
    """DataGrid whose wheel input participates in retained scroll bubbling."""

    _routed_scroll_unsubscribe: Callable[[], None] | None = None

    def on_mount(self, window: Window) -> None:
        """Replace the legacy window listener with component-targeted routing."""

        super().on_mount(window)

        legacy_unsubscribe = self._scroll_window_unsubscribe
        self._scroll_window_unsubscribe = None
        if legacy_unsubscribe is not None:
            legacy_unsubscribe()

        if self._routed_scroll_unsubscribe is None:
            self._routed_scroll_unsubscribe = self.on(
                "pointer_scroll",
                self._on_routed_pointer_scroll,
            )

    def on_unmount(self, window: Window) -> None:
        unsubscribe = self._routed_scroll_unsubscribe
        self._routed_scroll_unsubscribe = None
        if unsubscribe is not None:
            unsubscribe()
        super().on_unmount(window)

    def _on_routed_pointer_scroll(self, event: Event) -> None:
        if not self.enabled or not self.visible:
            return
        deltas = routed_scroll_deltas(event)
        if deltas is None:
            return

        remaining_x, remaining_y, consumed = self._consume_grid_scroll(
            delta_x=deltas[0],
            delta_y=deltas[1],
        )
        update_scroll_residual(
            event,
            delta_x=remaining_x,
            delta_y=remaining_y,
            consumed=consumed,
        )
