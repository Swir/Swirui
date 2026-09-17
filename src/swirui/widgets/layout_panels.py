"""Retained Stack, Grid and Wrap layout containers for SwirUI."""

from __future__ import annotations

import math

from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .layout import CrossAxisAlignment, Insets


class _PanelLayout(Widget):
    """Shared retained layout panel behavior."""

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
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._padding = padding if isinstance(padding, Insets) else Insets.all(padding)
        self._fill_viewport = bool(fill_viewport)

    @property
    def padding(self) -> Insets:
        return self._padding

    @padding.setter
    def padding(self, value: Insets | float) -> None:
        normalized = value if isinstance(value, Insets) else Insets.all(value)
        if normalized == self._padding:
            return
        self._padding = normalized
        self.invalidate(reason="layout_padding")

    @property
    def fill_viewport(self) -> bool:
        return self._fill_viewport

    @fill_viewport.setter
    def fill_viewport(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._fill_viewport:
            return
        self._fill_viewport = normalized
        self.invalidate(reason="fill_viewport")

    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=self.clip_to_bounds,
            hit_testable=False,
        )

    def _prepare_bounds(self, viewport: Rect) -> Rect:
        if self.fill_viewport:
            self._set_layout_bounds(viewport)
        padding = self.padding
        return Rect(
            self.bounds.x + padding.left,
            self.bounds.y + padding.top,
            max(0.0, self.bounds.width - padding.left - padding.right),
            max(0.0, self.bounds.height - padding.top - padding.bottom),
        )

    def _layout_children(self) -> tuple[Widget, ...]:
        return tuple(
            child for child in self.children if isinstance(child, Widget) and child.visible
        )

    def _add_padding(self, size: Size) -> Size:
        return Size(
            size.width + self.padding.left + self.padding.right,
            size.height + self.padding.top + self.padding.bottom,
        )


class Stack(_PanelLayout):
    """Overlay children inside one retained layout slot."""

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        horizontal_alignment: CrossAxisAlignment = CrossAxisAlignment.STRETCH,
        vertical_alignment: CrossAxisAlignment = CrossAxisAlignment.STRETCH,
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
        self._horizontal_alignment = CrossAxisAlignment(horizontal_alignment)
        self._vertical_alignment = CrossAxisAlignment(vertical_alignment)

    @property
    def horizontal_alignment(self) -> CrossAxisAlignment:
        return self._horizontal_alignment

    @horizontal_alignment.setter
    def horizontal_alignment(self, value: CrossAxisAlignment) -> None:
        normalized = CrossAxisAlignment(value)
        if normalized is self._horizontal_alignment:
            return
        self._horizontal_alignment = normalized
        self.invalidate(reason="horizontal_alignment")

    @property
    def vertical_alignment(self) -> CrossAxisAlignment:
        return self._vertical_alignment

    @vertical_alignment.setter
    def vertical_alignment(self, value: CrossAxisAlignment) -> None:
        normalized = CrossAxisAlignment(value)
        if normalized is self._vertical_alignment:
            return
        self._vertical_alignment = normalized
        self.invalidate(reason="vertical_alignment")

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
        available = content.size
        for child in self._layout_children():
            measured = child.measure(available)
            width = _aligned_extent(
                measured.width,
                content.width,
                child.layout_constraints.min_width,
                child.layout_constraints.max_width,
                self.horizontal_alignment,
            )
            height = _aligned_extent(
                measured.height,
                content.height,
                child.layout_constraints.min_height,
                child.layout_constraints.max_height,
                self.vertical_alignment,
            )
            child._set_layout_bounds(
                Rect(
                    _aligned_origin(content.x, content.width, width, self.horizontal_alignment),
                    _aligned_origin(content.y, content.height, height, self.vertical_alignment),
                    width,
                    height,
                )
            )


class Grid(_PanelLayout):
    """Arrange children in deterministic weighted row-major grid cells."""

    def __init__(
        self,
        *,
        bounds: Rect,
        columns: int = 1,
        column_weights: tuple[float, ...] | None = None,
        column_spacing: float = 0.0,
        row_spacing: float = 0.0,
        padding: Insets | float = 0.0,
        horizontal_alignment: CrossAxisAlignment = CrossAxisAlignment.STRETCH,
        vertical_alignment: CrossAxisAlignment = CrossAxisAlignment.START,
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
        self._columns = self._validate_columns(columns)
        self._column_weights = self._validate_weights(column_weights, self._columns)
        self._column_spacing = _validate_spacing(column_spacing, "column_spacing")
        self._row_spacing = _validate_spacing(row_spacing, "row_spacing")
        self._horizontal_alignment = CrossAxisAlignment(horizontal_alignment)
        self._vertical_alignment = CrossAxisAlignment(vertical_alignment)

    @property
    def columns(self) -> int:
        return self._columns

    @columns.setter
    def columns(self, value: int) -> None:
        normalized = self._validate_columns(value)
        if normalized == self._columns:
            return
        self._columns = normalized
        self._column_weights = tuple(1.0 for _ in range(normalized))
        self.invalidate(reason="grid_columns")

    @property
    def column_weights(self) -> tuple[float, ...]:
        return self._column_weights

    @column_weights.setter
    def column_weights(self, value: tuple[float, ...]) -> None:
        normalized = self._validate_weights(value, self.columns)
        if normalized == self._column_weights:
            return
        self._column_weights = normalized
        self.invalidate(reason="grid_column_weights")

    @property
    def column_spacing(self) -> float:
        return self._column_spacing

    @column_spacing.setter
    def column_spacing(self, value: float) -> None:
        normalized = _validate_spacing(value, "column_spacing")
        if normalized == self._column_spacing:
            return
        self._column_spacing = normalized
        self.invalidate(reason="grid_column_spacing")

    @property
    def row_spacing(self) -> float:
        return self._row_spacing

    @row_spacing.setter
    def row_spacing(self, value: float) -> None:
        normalized = _validate_spacing(value, "row_spacing")
        if normalized == self._row_spacing:
            return
        self._row_spacing = normalized
        self.invalidate(reason="grid_row_spacing")

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        if not children:
            return self.layout_constraints.constrain(self._add_padding(Size(0.0, 0.0)))
        sizes = [child.measure(available) for child in children]
        column_widths = [0.0] * self.columns
        row_heights: list[float] = []
        for index, size in enumerate(sizes):
            column = index % self.columns
            row = index // self.columns
            column_widths[column] = max(column_widths[column], size.width)
            if row == len(row_heights):
                row_heights.append(size.height)
            else:
                row_heights[row] = max(row_heights[row], size.height)
        natural = Size(
            sum(column_widths) + self.column_spacing * max(0, self.columns - 1),
            sum(row_heights) + self.row_spacing * max(0, len(row_heights) - 1),
        )
        return self.layout_constraints.constrain(self._add_padding(natural))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._prepare_bounds(viewport)
        children = self._layout_children()
        if not children:
            return

        total_column_gap = self.column_spacing * max(0, self.columns - 1)
        usable_width = max(0.0, content.width - total_column_gap)
        weight_total = sum(self.column_weights)
        column_widths = [
            usable_width * weight / weight_total for weight in self.column_weights
        ]
        measured: list[Size] = []
        row_heights: list[float] = []
        for index, child in enumerate(children):
            column = index % self.columns
            size = child.measure(Size(column_widths[column], content.height))
            measured.append(size)
            row = index // self.columns
            if row == len(row_heights):
                row_heights.append(size.height)
            else:
                row_heights[row] = max(row_heights[row], size.height)

        column_origins: list[float] = []
        cursor_x = content.x
        for width in column_widths:
            column_origins.append(cursor_x)
            cursor_x += width + self.column_spacing

        row_origins: list[float] = []
        cursor_y = content.y
        for height in row_heights:
            row_origins.append(cursor_y)
            cursor_y += height + self.row_spacing

        for index, (child, size) in enumerate(zip(children, measured, strict=True)):
            column = index % self.columns
            row = index // self.columns
            cell_width = column_widths[column]
            cell_height = row_heights[row]
            width = _aligned_extent(
                size.width,
                cell_width,
                child.layout_constraints.min_width,
                child.layout_constraints.max_width,
                self._horizontal_alignment,
            )
            height = _aligned_extent(
                size.height,
                cell_height,
                child.layout_constraints.min_height,
                child.layout_constraints.max_height,
                self._vertical_alignment,
            )
            child._set_layout_bounds(
                Rect(
                    _aligned_origin(
                        column_origins[column],
                        cell_width,
                        width,
                        self._horizontal_alignment,
                    ),
                    _aligned_origin(
                        row_origins[row],
                        cell_height,
                        height,
                        self._vertical_alignment,
                    ),
                    width,
                    height,
                )
            )

    @staticmethod
    def _validate_columns(value: int) -> int:
        normalized = int(value)
        if normalized < 1:
            raise ValueError("columns must be at least 1.")
        return normalized

    @staticmethod
    def _validate_weights(
        value: tuple[float, ...] | None,
        columns: int,
    ) -> tuple[float, ...]:
        weights = tuple(1.0 for _ in range(columns)) if value is None else tuple(value)
        if len(weights) != columns:
            raise ValueError("column_weights must contain exactly one value per column.")
        if any(not math.isfinite(weight) or weight <= 0.0 for weight in weights):
            raise ValueError("column_weights must contain finite positive values.")
        return weights


class Wrap(_PanelLayout):
    """Flow children horizontally and wrap complete items onto new rows."""

    def __init__(
        self,
        *,
        bounds: Rect,
        spacing: float = 0.0,
        run_spacing: float = 0.0,
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
        self._spacing = _validate_spacing(spacing, "spacing")
        self._run_spacing = _validate_spacing(run_spacing, "run_spacing")
        self._run_alignment = CrossAxisAlignment(run_alignment)

    @property
    def spacing(self) -> float:
        return self._spacing

    @spacing.setter
    def spacing(self, value: float) -> None:
        normalized = _validate_spacing(value, "spacing")
        if normalized == self._spacing:
            return
        self._spacing = normalized
        self.invalidate(reason="wrap_spacing")

    @property
    def run_spacing(self) -> float:
        return self._run_spacing

    @run_spacing.setter
    def run_spacing(self, value: float) -> None:
        normalized = _validate_spacing(value, "run_spacing")
        if normalized == self._run_spacing:
            return
        self._run_spacing = normalized
        self.invalidate(reason="wrap_run_spacing")

    @property
    def run_alignment(self) -> CrossAxisAlignment:
        return self._run_alignment

    @run_alignment.setter
    def run_alignment(self, value: CrossAxisAlignment) -> None:
        normalized = CrossAxisAlignment(value)
        if normalized is self._run_alignment:
            return
        self._run_alignment = normalized
        self.invalidate(reason="wrap_run_alignment")

    def measure(self, available: Size | None = None) -> Size:
        limit = self.bounds.width
        if available is not None:
            limit = available.width
        inner_limit = max(0.0, limit - self.padding.left - self.padding.right)
        lines = self._lines(inner_limit, available)
        width = max(
            (
                sum(size.width for _child, size in line)
                + self.spacing * max(0, len(line) - 1)
                for line in lines
            ),
            default=0.0,
        )
        height = sum(max(size.height for _child, size in line) for line in lines)
        height += self.run_spacing * max(0, len(lines) - 1)
        return self.layout_constraints.constrain(self._add_padding(Size(width, height)))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._prepare_bounds(viewport)
        lines = self._lines(content.width, content.size)
        cursor_y = content.y
        for line in lines:
            line_height = max(size.height for _child, size in line)
            cursor_x = content.x
            for child, size in line:
                height = _aligned_extent(
                    size.height,
                    line_height,
                    child.layout_constraints.min_height,
                    child.layout_constraints.max_height,
                    self.run_alignment,
                )
                child._set_layout_bounds(
                    Rect(
                        cursor_x,
                        _aligned_origin(
                            cursor_y,
                            line_height,
                            height,
                            self.run_alignment,
                        ),
                        size.width,
                        height,
                    )
                )
                cursor_x += size.width + self.spacing
            cursor_y += line_height + self.run_spacing

    def _lines(
        self,
        width: float,
        available: Size | None,
    ) -> list[list[tuple[Widget, Size]]]:
        lines: list[list[tuple[Widget, Size]]] = []
        current: list[tuple[Widget, Size]] = []
        occupied = 0.0
        measure_available = available or Size(max(0.0, width), math.inf)

        for child in self._layout_children():
            size = child.measure(measure_available)
            needed = size.width if not current else self.spacing + size.width
            if current and occupied + needed > width:
                lines.append(current)
                current = []
                occupied = 0.0
                needed = size.width
            current.append((child, size))
            occupied += needed
        if current:
            lines.append(current)
        return lines


def _validate_spacing(value: float, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be a finite non-negative value.")
    return normalized


def _aligned_extent(
    measured: float,
    available: float,
    minimum: float,
    maximum: float,
    alignment: CrossAxisAlignment,
) -> float:
    target = available if alignment is CrossAxisAlignment.STRETCH else measured
    return min(max(target, minimum), maximum)


def _aligned_origin(
    origin: float,
    available: float,
    extent: float,
    alignment: CrossAxisAlignment,
) -> float:
    remaining = max(0.0, available - extent)
    if alignment is CrossAxisAlignment.CENTER:
        return origin + remaining / 2.0
    if alignment is CrossAxisAlignment.END:
        return origin + remaining
    return origin
