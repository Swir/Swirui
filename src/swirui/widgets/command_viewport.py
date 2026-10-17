"""Bounded row viewport shared by retained popup command surfaces."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from swirui.core import Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .scroll_events import routed_scroll_deltas, update_scroll_residual

if TYPE_CHECKING:
    from .base import Widget


class CommandViewport:
    """Pixel scrolling with bounded compilation and a captured scrollbar thumb."""

    def __init__(self) -> None:
        self.bounds = Rect(0, 0, 0, 0)
        self.row_height = 1.0
        self.count = 0
        self.offset = 0.0
        self._drag_anchor: float | None = None
        self._follow_index: int | None = None

    @property
    def maximum(self) -> float:
        return max(0.0, self.count * self.row_height - self.bounds.height)

    @property
    def content_width(self) -> float:
        return max(0.0, self.bounds.width - (12.0 if self.maximum else 0.0))

    def configure(self, bounds: Rect, row_height: float, count: int) -> None:
        resized = bounds != self.bounds
        self.bounds, self.row_height, self.count = bounds, row_height, count
        self.offset = min(max(0.0, self.offset), self.maximum)
        if resized and self._follow_index is not None:
            self.reveal(self._follow_index)

    def reveal(self, index: int | None) -> None:
        self._follow_index = index
        if index is None or self.bounds.height <= 0:
            return
        top = index * self.row_height
        if top < self.offset:
            self.offset = top
        elif top + self.row_height > self.offset + self.bounds.height:
            self.offset = top + self.row_height - self.bounds.height
        self.offset = min(max(0.0, self.offset), self.maximum)

    def visible_indices(self) -> range:
        if self.bounds.height <= 0 or self.bounds.width <= 0:
            return range(0)
        return range(
            int(self.offset // self.row_height),
            min(self.count, math.ceil((self.offset + self.bounds.height) / self.row_height)),
        )

    def row_bounds(self, index: int) -> Rect:
        return Rect(
            self.bounds.x,
            self.bounds.y + index * self.row_height - self.offset,
            self.content_width,
            self.row_height,
        )

    def scroll_by(self, delta: float) -> float:
        if not math.isfinite(delta):
            raise ValueError("Command scroll delta must be finite.")
        before = self.offset
        self.offset = min(max(0.0, before + delta), self.maximum)
        if self.offset != before:
            self._follow_index = None
        return self.offset - before

    def on_scroll(self, owner: Widget, event: Event) -> None:
        native = event.data.get("event")
        if (
            not owner.enabled
            or not owner.visible
            or not isinstance(native, PlatformEvent)
            or not self._contains(self.bounds, native.x, native.y)
        ):
            return
        deltas = routed_scroll_deltas(event)
        if deltas is None:
            return
        dx, dy = deltas
        consumed = self.scroll_by(dy)
        if consumed:
            owner.invalidate(reason="scroll_offset")
        update_scroll_residual(event, delta_x=dx, delta_y=dy - consumed, consumed=consumed != 0)

    def scrollbar(self) -> tuple[Rect, Rect] | None:
        if not self.maximum or self.bounds.height <= 6 or self.bounds.width < 12:
            return None
        track = Rect(self.bounds.right - 8, self.bounds.y + 3, 5, self.bounds.height - 6)
        height = min(
            track.height,
            max(20.0, track.height * self.bounds.height / (self.count * self.row_height)),
        )
        thumb = Rect(
            track.x,
            track.y + (track.height - height) * self.offset / self.maximum,
            track.width,
            height,
        )
        return track, thumb

    def add_scrollbar(
        self, root: SceneNode, key: str, track_color: Color, thumb_color: Color
    ) -> None:
        geometry = self.scrollbar()
        if geometry is None:
            return
        for suffix, bounds, color in (
            ("track", geometry[0], track_color),
            ("thumb", geometry[1], thumb_color),
        ):
            root.add(
                SceneNode(
                    key=f"{key}:scrollbar:{suffix}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=bounds,
                    fill=color,
                    corner_radius=CornerRadius.uniform(2.5),
                    z_index=9000,
                    hit_testable=False,
                )
            )

    def on_pointer_down(self, owner: Widget, event: Event) -> bool:
        native = event.data.get("event")
        geometry = self.scrollbar()
        if (
            not owner.enabled
            or not owner.visible
            or geometry is None
            or not isinstance(native, PlatformEvent)
            or native.button is not PointerButton.LEFT
            or native.x is None
            or native.y is None
            or not self._contains(
                Rect(self.bounds.right - 12, self.bounds.y, 12, self.bounds.height),
                native.x,
                native.y,
            )
        ):
            return False
        _track, thumb = geometry
        if thumb.y <= native.y < thumb.bottom:
            self._drag_anchor = native.y - thumb.y
            if owner.mounted_window:
                owner.mounted_window.capture_pointer(owner)
        else:
            consumed = self.scroll_by(self.bounds.height * (-1 if native.y < thumb.y else 1))
            if consumed:
                owner.invalidate(reason="scroll_offset")
        event.prevent_default()
        return True

    def on_pointer_move(self, owner: Widget, event: Event) -> None:
        if self._drag_anchor is None:
            return
        window = owner.mounted_window
        if window is None or window.pointer_capture_component is not owner:
            self._drag_anchor = None
            return
        native = event.data.get("event")
        geometry = self.scrollbar()
        if not isinstance(native, PlatformEvent) or native.y is None or geometry is None:
            return
        track, thumb = geometry
        travel = track.height - thumb.height
        target = (
            0.0 if travel <= 0 else (native.y - track.y - self._drag_anchor) * self.maximum / travel
        )
        if self.scroll_by(target - self.offset):
            owner.invalidate(reason="scroll_offset")
        event.prevent_default()

    def on_pointer_up(self, owner: Widget, event: Event) -> None:
        native = event.data.get("event")
        if not isinstance(native, PlatformEvent) or native.kind is not PlatformEventKind.POINTER_UP:
            return
        if self._drag_anchor is not None:
            self._drag_anchor = None
            if owner.mounted_window and owner.mounted_window.pointer_capture_component is owner:
                owner.mounted_window.release_pointer_capture()
            event.prevent_default()

    @staticmethod
    def _contains(bounds: Rect, x: float | None, y: float | None) -> bool:
        return (
            x is not None
            and y is not None
            and bounds.x <= x < bounds.right
            and bounds.y <= y < bounds.bottom
        )
