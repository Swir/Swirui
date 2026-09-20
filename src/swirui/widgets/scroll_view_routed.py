"""Native wheel/trackpad routing for the retained ScrollView."""

from __future__ import annotations

from swirui.core import Event
from swirui.rendering.geometry import Rect

from .scroll_events import routed_scroll_deltas, update_scroll_residual
from .scrolling import ScrollView as _ScrollView


class ScrollView(_ScrollView):
    """ScrollView with routed high-resolution wheel/trackpad consumption."""

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        content_width: float | None = None,
        content_height: float | None = None,
        scroll_x: float = 0.0,
        scroll_y: float = 0.0,
        line_step: float = 40.0,
        page_overlap: float = 24.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            bounds=bounds,
            key=key,
            content_width=content_width,
            content_height=content_height,
            scroll_x=scroll_x,
            scroll_y=scroll_y,
            line_step=line_step,
            page_overlap=page_overlap,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_scroll", self._on_pointer_scroll)

    def _on_pointer_scroll(self, event: Event) -> None:
        if not self.enabled or not self.visible:
            return
        deltas = routed_scroll_deltas(event)
        if deltas is None:
            return

        delta_x, delta_y = deltas
        before_x = self.scroll_x
        before_y = self.scroll_y
        self.scroll_by(dx=delta_x, dy=delta_y)
        consumed_x = self.scroll_x - before_x
        consumed_y = self.scroll_y - before_y
        update_scroll_residual(
            event,
            delta_x=delta_x - consumed_x,
            delta_y=delta_y - consumed_y,
            consumed=consumed_x != 0.0 or consumed_y != 0.0,
        )
