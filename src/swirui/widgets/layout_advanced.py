"""Advanced retained Dock, Flow and Overlay layout containers for SwirUI."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from swirui.core import Component
from swirui.rendering.geometry import Rect, Size

from .base import Widget
from .layout import CrossAxisAlignment, Insets
from .layout_panels import _PanelLayout, _aligned_extent, _aligned_origin, _validate_spacing


class DockSide(StrEnum):
    """Edge consumed by a child inside :class:`Dock`."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    FILL = "fill"


class Dock(_PanelLayout):
    """Consume a retained content rectangle from its edges in child order.

    Children added with the ordinary ``add`` API default to ``FILL``. Use
    :meth:`add_docked` or :meth:`set_dock` for explicit edge placement.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._dock_sides: dict[Widget, DockSide] = {}

    def add_docked(self, child: Widget, side: DockSide = DockSide.FILL) -> Dock:
        """Add ``child`` with an explicit dock side using one invalidation."""

        normalized = DockSide(side)
        if child.parent is self:
            return self.set_dock(child, normalized)
        self._dock_sides[child] = normalized
        self.add(child)
        return self

    def set_dock(self, child: Widget, side: DockSide) -> Dock:
        """Change an existing child's dock side and invalidate layout once."""

        if child.parent is not self:
            raise ValueError("Dock placement can only be changed for a direct child.")
        normalized = DockSide(side)
        if self._dock_sides.get(child, DockSide.FILL) is normalized:
            return self
        self._dock_sides[child] = normalized
        self.invalidate(reason="dock_side", source=child)
        return self

    def dock_for(self, child: Widget) -> DockSide:
        """Return a direct child's effective dock side."""

        if child.parent is not self:
            raise ValueError("Dock placement is only defined for direct children.")
        return self._dock_sides.get(child, DockSide.FILL)

    def remove(self, child: Component) -> Component:
        removed = super().remove(child)
        if isinstance(child, Widget):
            self._dock_sides.pop(child, None)
        return removed

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        if not children:
            return self.layout_constraints.constrain(self._add_padding(Size(0.0, 0.0)))

        sizes = [(child, child.measure(available)) for child in children]
        horizontal = sum(
            size.width
            for child, size in sizes
            if self._dock_sides.get(child, DockSide.FILL) in {DockSide.LEFT, DockSide.RIGHT}
        )
        vertical = sum(
            size.height
            for child, size in sizes
            if self._dock_sides.get(child, DockSide.FILL) in {DockSide.TOP, DockSide.BOTTOM}
        )
        center_width = max(
            (
                size.width
                for child, size in sizes
                if self._dock_sides.get(child, DockSide.FILL)
                in {DockSide.TOP, DockSide.BOTTOM, DockSide.FILL}
            ),
            default=0.0,
        )
        center_height = max(
            (
                size.height
                for child, size in sizes
                if self._dock_sides.get(child, DockSide.FILL)
                in {DockSide.LEFT, DockSide.RIGHT, DockSide.FILL}
            ),
            default=0.0,
        )
        return self.layout_constraints.constrain(
            self._add_padding(Size(horizontal + center_width, vertical + center_height))
        )

    def prepare_layout(self, viewport: Rect) -> None:
        remaining = self._prepare_bounds(viewport)
        for child in self._layout_children():
            side = self._dock_sides.get(child, DockSide.FILL)
            measured = child.measure(remaining.size)
            constraints = child.layout_constraints

            if side in {DockSide.LEFT, DockSide.RIGHT}:
                width = measured.width
                height = _aligned_extent(
                    measured.height,
                    remaining.height,
                    constraints.min_height,
                    constraints.max_height,
                    CrossAxisAlignment.STRETCH,
                )
                x = remaining.x if side is DockSide.LEFT else remaining.right - width
                y = _aligned_origin(
                    remaining.y,
                    remaining.height,
                    height,
                    CrossAxisAlignment.START,
                )
                child._set_layout_bounds(Rect(x, y, width, height))
                consumed = min(width, remaining.width)
                if side is DockSide.LEFT:
                    remaining = Rect(
                        remaining.x + consumed,
                        remaining.y,
                        max(0.0, remaining.width - consumed),
                        remaining.height,
                    )
                else:
                    remaining = Rect(
                        remaining.x,
                        remaining.y,
                        max(0.0, remaining.width - consumed),
                        remaining.height,
                    )
                continue

            if side in {DockSide.TOP, DockSide.BOTTOM}:
                width = _aligned_extent(
                    measured.width,
                    remaining.width,
                    constraints.min_width,
                    constraints.max_width,
                    CrossAxisAlignment.STRETCH,
                )
                height = measured.height
                x = _aligned_origin(
                    remaining.x,
                    remaining.width,
                    width,
                    CrossAxisAlignment.START,
                )
                y = remaining.y if side is DockSide.TOP else remaining.bottom - height
                child._set_layout_bounds(Rect(x, y, width, height))
                consumed = min(height, remaining.height)
                if side is DockSide.TOP:
                    remaining = Rect(
                        remaining.x,
                        remaining.y + consumed,
                        remaining.width,
                        max(0.0, remaining.height - consumed),
                    )
                else:
                    remaining = Rect(
                        remaining.x,
                        remaining.y,
                        remaining.width,
                        max(0.0, remaining.height - consumed),
                    )
                continue

            width = _aligned_extent(
                measured.width,
                remaining.width,
                constraints.min_width,
                constraints.max_width,
                CrossAxisAlignment.STRETCH,
            )
            height = _aligned_extent(
                measured.height,
                remaining.height,
                constraints.min_height,
                constraints.max_height,
                CrossAxisAlignment.STRETCH,
            )
            child._set_layout_bounds(
                Rect(
                    _aligned_origin(
                        remaining.x,
                        remaining.width,
                        width,
                        CrossAxisAlignment.START,
                    ),
                    _aligned_origin(
                        remaining.y,
                        remaining.height,
                        height,
                        CrossAxisAlignment.START,
                    ),
                    width,
                    height,
                )
            )


class FlowOrientation(StrEnum):
    """Primary axis used by :class:`Flow`."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class Flow(_PanelLayout):
    """Directional retained flow layout with optional wrapping and reversal."""

    def __init__(
        self,
        *,
        bounds: Rect,
        orientation: FlowOrientation = FlowOrientation.HORIZONTAL,
        spacing: float = 0.0,
        run_spacing: float = 0.0,
        wrap: bool = True,
        reverse: bool = False,
        padding: Insets | float = 0.0,
        run_alignment: CrossAxisAlignment = CrossAxisAlignment.START,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._orientation = FlowOrientation(orientation)
        self._spacing = _validate_spacing(spacing, "spacing")
        self._run_spacing = _validate_spacing(run_spacing, "run_spacing")
        self._wrap = bool(wrap)
        self._reverse = bool(reverse)
        self._run_alignment = CrossAxisAlignment(run_alignment)

    @property
    def orientation(self) -> FlowOrientation:
        return self._orientation

    @orientation.setter
    def orientation(self, value: FlowOrientation) -> None:
        normalized = FlowOrientation(value)
        if normalized is self._orientation:
            return
        self._orientation = normalized
        self.invalidate(reason="flow_orientation")

    @property
    def spacing(self) -> float:
        return self._spacing

    @spacing.setter
    def spacing(self, value: float) -> None:
        normalized = _validate_spacing(value, "spacing")
        if normalized == self._spacing:
            return
        self._spacing = normalized
        self.invalidate(reason="flow_spacing")

    @property
    def run_spacing(self) -> float:
        return self._run_spacing

    @run_spacing.setter
    def run_spacing(self, value: float) -> None:
        normalized = _validate_spacing(value, "run_spacing")
        if normalized == self._run_spacing:
            return
        self._run_spacing = normalized
        self.invalidate(reason="flow_run_spacing")

    @property
    def wrap(self) -> bool:
        return self._wrap

    @wrap.setter
    def wrap(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._wrap:
            return
        self._wrap = normalized
        self.invalidate(reason="flow_wrap")

    @property
    def reverse(self) -> bool:
        return self._reverse

    @reverse.setter
    def reverse(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._reverse:
            return
        self._reverse = normalized
        self.invalidate(reason="flow_reverse")

    @property
    def run_alignment(self) -> CrossAxisAlignment:
        return self._run_alignment

    @run_alignment.setter
    def run_alignment(self, value: CrossAxisAlignment) -> None:
        normalized = CrossAxisAlignment(value)
        if normalized is self._run_alignment:
            return
        self._run_alignment = normalized
        self.invalidate(reason="flow_run_alignment")

    def measure(self, available: Size | None = None) -> Size:
        main_limit = self._main_limit(available)
        runs = self._runs(main_limit, available)
        main = max(
            (
                sum(self._main_size(size) for _child, size in run)
                + self.spacing * max(0, len(run) - 1)
                for run in runs
            ),
            default=0.0,
        )
        cross = sum(
            max(self._cross_size(size) for _child, size in run) for run in runs
        )
        cross += self.run_spacing * max(0, len(runs) - 1)
        natural = Size(main, cross) if self.orientation is FlowOrientation.HORIZONTAL else Size(cross, main)
        return self.layout_constraints.constrain(self._add_padding(natural))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._prepare_bounds(viewport)
        main_limit = content.width if self.orientation is FlowOrientation.HORIZONTAL else content.height
        runs = self._runs(main_limit, content.size)
        run_cursor = content.y if self.orientation is FlowOrientation.HORIZONTAL else content.x

        for run in runs:
            run_cross = max(self._cross_size(size) for _child, size in run)
            item_cursor = content.x if self.orientation is FlowOrientation.HORIZONTAL else content.y
            for child, size in run:
                constraints = child.layout_constraints
                if self.orientation is FlowOrientation.HORIZONTAL:
                    cross = _aligned_extent(
                        size.height,
                        run_cross,
                        constraints.min_height,
                        constraints.max_height,
                        self.run_alignment,
                    )
                    child._set_layout_bounds(
                        Rect(
                            item_cursor,
                            _aligned_origin(run_cursor, run_cross, cross, self.run_alignment),
                            size.width,
                            cross,
                        )
                    )
                    item_cursor += size.width + self.spacing
                else:
                    cross = _aligned_extent(
                        size.width,
                        run_cross,
                        constraints.min_width,
                        constraints.max_width,
                        self.run_alignment,
                    )
                    child._set_layout_bounds(
                        Rect(
                            _aligned_origin(run_cursor, run_cross, cross, self.run_alignment),
                            item_cursor,
                            cross,
                            size.height,
                        )
                    )
                    item_cursor += size.height + self.spacing
            run_cursor += run_cross + self.run_spacing

    def _main_limit(self, available: Size | None) -> float:
        if available is not None:
            raw = available.width if self.orientation is FlowOrientation.HORIZONTAL else available.height
        else:
            raw = self.bounds.width if self.orientation is FlowOrientation.HORIZONTAL else self.bounds.height
        padding = (
            self.padding.left + self.padding.right
            if self.orientation is FlowOrientation.HORIZONTAL
            else self.padding.top + self.padding.bottom
        )
        return max(0.0, raw - padding)

    def _runs(
        self,
        main_limit: float,
        available: Size | None,
    ) -> list[list[tuple[Widget, Size]]]:
        children = list(self._layout_children())
        if self.reverse:
            children.reverse()

        if available is None:
            measure_available = (
                Size(main_limit, math.inf)
                if self.orientation is FlowOrientation.HORIZONTAL
                else Size(math.inf, main_limit)
            )
        else:
            measure_available = available

        runs: list[list[tuple[Widget, Size]]] = []
        current: list[tuple[Widget, Size]] = []
        occupied = 0.0
        for child in children:
            size = child.measure(measure_available)
            main = self._main_size(size)
            needed = main if not current else self.spacing + main
            if self.wrap and current and occupied + needed > main_limit:
                runs.append(current)
                current = []
                occupied = 0.0
                needed = main
            current.append((child, size))
            occupied += needed
        if current:
            runs.append(current)
        return runs

    def _main_size(self, size: Size) -> float:
        return size.width if self.orientation is FlowOrientation.HORIZONTAL else size.height

    def _cross_size(self, size: Size) -> float:
        return size.height if self.orientation is FlowOrientation.HORIZONTAL else size.width


class OverlayAnchor(StrEnum):
    """Anchor used for one child inside :class:`Overlay`."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    STRETCH = "stretch"


@dataclass(frozen=True, slots=True)
class _OverlayPlacement:
    anchor: OverlayAnchor
    offset_x: float
    offset_y: float


class Overlay(_PanelLayout):
    """Anchor independent retained children inside one overlay surface."""

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._placements: dict[Widget, _OverlayPlacement] = {}

    def add_overlay(
        self,
        child: Widget,
        *,
        anchor: OverlayAnchor = OverlayAnchor.TOP_LEFT,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> Overlay:
        """Add ``child`` with an anchor and logical-DIP offset."""

        placement = self._placement(anchor, offset_x, offset_y)
        if child.parent is self:
            return self.set_overlay(
                child,
                anchor=placement.anchor,
                offset_x=placement.offset_x,
                offset_y=placement.offset_y,
            )
        self._placements[child] = placement
        self.add(child)
        return self

    def set_overlay(
        self,
        child: Widget,
        *,
        anchor: OverlayAnchor,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> Overlay:
        """Update a direct child's anchored overlay placement."""

        if child.parent is not self:
            raise ValueError("Overlay placement can only be changed for a direct child.")
        placement = self._placement(anchor, offset_x, offset_y)
        if self._placements.get(child, self._placement(OverlayAnchor.TOP_LEFT, 0.0, 0.0)) == placement:
            return self
        self._placements[child] = placement
        self.invalidate(reason="overlay_placement", source=child)
        return self

    def remove(self, child: Component) -> Component:
        removed = super().remove(child)
        if isinstance(child, Widget):
            self._placements.pop(child, None)
        return removed

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        if not children:
            return self.layout_constraints.constrain(self._add_padding(Size(0.0, 0.0)))
        sizes = [child.measure(available) for child in children]
        natural = Size(
            max(size.width for size in sizes),
            max(size.height for size in sizes),
        )
        return self.layout_constraints.constrain(self._add_padding(natural))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._prepare_bounds(viewport)
        for child in self._layout_children():
            placement = self._placements.get(
                child,
                _OverlayPlacement(OverlayAnchor.TOP_LEFT, 0.0, 0.0),
            )
            measured = child.measure(content.size)
            constraints = child.layout_constraints
            if placement.anchor is OverlayAnchor.STRETCH:
                width = _aligned_extent(
                    measured.width,
                    content.width,
                    constraints.min_width,
                    constraints.max_width,
                    CrossAxisAlignment.STRETCH,
                )
                height = _aligned_extent(
                    measured.height,
                    content.height,
                    constraints.min_height,
                    constraints.max_height,
                    CrossAxisAlignment.STRETCH,
                )
            else:
                width = measured.width
                height = measured.height

            x = self._anchored_x(content, width, placement.anchor) + placement.offset_x
            y = self._anchored_y(content, height, placement.anchor) + placement.offset_y
            child._set_layout_bounds(Rect(x, y, width, height))

    @staticmethod
    def _placement(
        anchor: OverlayAnchor,
        offset_x: float,
        offset_y: float,
    ) -> _OverlayPlacement:
        normalized_x = float(offset_x)
        normalized_y = float(offset_y)
        if not math.isfinite(normalized_x) or not math.isfinite(normalized_y):
            raise ValueError("Overlay offsets must be finite logical-DIP values.")
        return _OverlayPlacement(OverlayAnchor(anchor), normalized_x, normalized_y)

    @staticmethod
    def _anchored_x(content: Rect, width: float, anchor: OverlayAnchor) -> float:
        if anchor in {
            OverlayAnchor.TOP_CENTER,
            OverlayAnchor.CENTER,
            OverlayAnchor.BOTTOM_CENTER,
        }:
            return content.x + max(0.0, content.width - width) / 2.0
        if anchor in {
            OverlayAnchor.TOP_RIGHT,
            OverlayAnchor.CENTER_RIGHT,
            OverlayAnchor.BOTTOM_RIGHT,
        }:
            return content.right - width
        return content.x

    @staticmethod
    def _anchored_y(content: Rect, height: float, anchor: OverlayAnchor) -> float:
        if anchor in {
            OverlayAnchor.CENTER_LEFT,
            OverlayAnchor.CENTER,
            OverlayAnchor.CENTER_RIGHT,
        }:
            return content.y + max(0.0, content.height - height) / 2.0
        if anchor in {
            OverlayAnchor.BOTTOM_LEFT,
            OverlayAnchor.BOTTOM_CENTER,
            OverlayAnchor.BOTTOM_RIGHT,
        }:
            return content.bottom - height
        return content.y
