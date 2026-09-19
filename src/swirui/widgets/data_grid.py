"""Retained virtualized data grid for professional desktop tables."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_HOME = 0x24
_VK_END = 0x23
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_UP = 0x26
_VK_DOWN = 0x28

_DEFAULT_BACKGROUND = Color.from_hex("#07111C")
_DEFAULT_HEADER_BACKGROUND = Color.from_hex("#0A1D2B")
_DEFAULT_ROW_BACKGROUND = Color.from_hex("#081723")
_DEFAULT_ALTERNATE_ROW_BACKGROUND = Color.from_hex("#0A1A28")
_DEFAULT_SELECTED_BACKGROUND = Color.from_hex("#0B4F77")
_DEFAULT_FOREGROUND = Color.from_hex("#DDF5FF")
_DEFAULT_HEADER_FOREGROUND = Color.from_hex("#62E5FF")
_DEFAULT_GRID_LINE = Color.from_hex("#17384A")


@dataclass(frozen=True, slots=True)
class DataGridColumn:
    """Describe one retained DataGrid column in logical DIPs."""

    key: str
    header: str
    width: float = 160.0
    min_width: float = 48.0
    max_width: float = math.inf

    def __post_init__(self) -> None:
        normalized_key = self.key.strip()
        if not normalized_key:
            raise ValueError("DataGridColumn.key must not be empty.")
        if not math.isfinite(self.width) or self.width <= 0.0:
            raise ValueError("DataGridColumn.width must be finite and positive.")
        if not math.isfinite(self.min_width) or self.min_width <= 0.0:
            raise ValueError("DataGridColumn.min_width must be finite and positive.")
        if math.isnan(self.max_width) or self.max_width <= 0.0:
            raise ValueError("DataGridColumn.max_width must be positive and not NaN.")
        if self.min_width > self.max_width:
            raise ValueError("DataGridColumn.min_width cannot exceed max_width.")

    @property
    def resolved_width(self) -> float:
        """Return the validated width after min/max constraints."""

        return min(max(self.width, self.min_width), self.max_width)


class DataGrid(Widget):
    """Focusable retained table with row virtualization and keyboard selection.

    Rows are retained as immutable snapshots of mappings while only the visible
    viewport is compiled to SceneGraph nodes. Selection and scrolling therefore
    stay deterministic for large datasets without creating one scene subtree per
    off-screen row.
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
    ) -> None:
        normalized_columns = tuple(columns)
        if not normalized_columns:
            raise ValueError("DataGrid requires at least one column.")
        column_keys = [column.key for column in normalized_columns]
        if len(column_keys) != len(set(column_keys)):
            raise ValueError("DataGrid column keys must be unique.")

        self._columns = normalized_columns
        self._rows = self._snapshot_rows(rows)
        self._row_height = self._validate_positive(row_height, "row_height")
        self._header_height = self._validate_positive(header_height, "header_height")
        self._cell_padding = self._validate_non_negative(cell_padding, "cell_padding")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = str(font_family).strip()
        if not self._font_family:
            raise ValueError("font_family must not be empty.")
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._background = background or _DEFAULT_BACKGROUND
        self._header_background = header_background or _DEFAULT_HEADER_BACKGROUND
        self._row_background = row_background or _DEFAULT_ROW_BACKGROUND
        self._alternate_row_background = (
            alternate_row_background or _DEFAULT_ALTERNATE_ROW_BACKGROUND
        )
        self._selected_background = selected_background or _DEFAULT_SELECTED_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._header_foreground = header_foreground or _DEFAULT_HEADER_FOREGROUND
        self._grid_line = grid_line or _DEFAULT_GRID_LINE
        self._selected_index: int | None = None
        self._scroll_offset = 0.0

        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.LIST,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)

    @property
    def columns(self) -> tuple[DataGridColumn, ...]:
        return self._columns

    @property
    def rows(self) -> tuple[Mapping[str, object], ...]:
        return self._rows

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def selected_row(self) -> Mapping[str, object] | None:
        if self._selected_index is None:
            return None
        return self._rows[self._selected_index]

    @property
    def scroll_offset(self) -> float:
        return self._effective_scroll_offset()

    @property
    def visible_row_range(self) -> range:
        """Return the row-index range that intersects the current viewport."""

        if not self._rows or self._body_height() <= 0.0:
            return range(0)
        offset = self._effective_scroll_offset()
        first = min(len(self._rows) - 1, int(offset // self._row_height))
        partial = offset - (first * self._row_height)
        visible_height = self._body_height() + partial
        count = max(1, math.ceil(visible_height / self._row_height))
        return range(first, min(len(self._rows), first + count))

    def set_rows(self, rows: Sequence[Mapping[str, object]]) -> DataGrid:
        """Replace the row snapshot while keeping selection valid."""

        normalized = self._snapshot_rows(rows)
        if normalized == self._rows:
            return self
        self._rows = normalized
        if self._selected_index is not None and self._selected_index >= len(self._rows):
            self._selected_index = None
        self._scroll_offset = min(self._scroll_offset, self._max_scroll_offset())
        self.invalidate(reason="rows")
        return self

    def select_row(self, index: int | None, *, ensure_visible: bool = True) -> DataGrid:
        """Select a row and optionally scroll it into the retained viewport."""

        normalized: int | None
        if index is None:
            normalized = None
        else:
            normalized = int(index)
            if not 0 <= normalized < len(self._rows):
                raise IndexError("DataGrid row index is out of range.")
        if normalized == self._selected_index:
            if normalized is not None and ensure_visible:
                self.scroll_to_row(normalized)
            return self

        self._selected_index = normalized
        if normalized is not None and ensure_visible:
            self.scroll_to_row(normalized)
        self.invalidate(reason="selection")
        self.emit(
            "selection_changed",
            index=normalized,
            row=None if normalized is None else self._rows[normalized],
        )
        return self

    def scroll_by(self, delta: float) -> DataGrid:
        """Scroll vertically by logical DIPs and clamp to available content."""

        normalized = float(delta)
        if not math.isfinite(normalized):
            raise ValueError("DataGrid scroll delta must be finite.")
        return self._set_scroll_offset(self._scroll_offset + normalized)

    def scroll_to_row(self, index: int) -> DataGrid:
        """Ensure one row is fully visible without changing selection."""

        normalized = int(index)
        if not 0 <= normalized < len(self._rows):
            raise IndexError("DataGrid row index is out of range.")
        body_height = self._body_height()
        if body_height <= 0.0:
            return self
        row_top = normalized * self._row_height
        row_bottom = row_top + self._row_height
        offset = self._effective_scroll_offset()
        if row_top < offset:
            return self._set_scroll_offset(row_top)
        if row_bottom > offset + body_height:
            return self._set_scroll_offset(row_bottom - body_height)
        return self

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        self._append_header(root)
        self._append_visible_rows(root)
        self._append_column_separators(root)
        return root

    def _append_header(self, root: SceneNode) -> None:
        header_bounds = Rect(
            self.bounds.x,
            self.bounds.y,
            self.bounds.width,
            min(self._header_height, self.bounds.height),
        )
        header = SceneNode(
            key=f"{self.key}:header",
            kind=SceneNodeKind.RECTANGLE,
            bounds=header_bounds,
            fill=self._header_background,
            z_index=3,
            clip_to_bounds=True,
            hit_testable=False,
        )
        x = self.bounds.x
        for column in self._columns:
            width = column.resolved_width
            cell_bounds = Rect(x, self.bounds.y, width, self._header_height)
            header.add(self._text_node(
                key=f"{self.key}:header:{column.key}",
                bounds=cell_bounds,
                text=column.header,
                color=self._header_foreground,
                font_size=self._font_size,
            ))
            x += width
        root.add(header)

    def _append_visible_rows(self, root: SceneNode) -> None:
        body_top = self.bounds.y + self._header_height
        body_bottom = self.bounds.y + self.bounds.height
        if body_top >= body_bottom:
            return
        offset = self._effective_scroll_offset()
        for index in self.visible_row_range:
            y = body_top + (index * self._row_height) - offset
            row_bounds = Rect(self.bounds.x, y, self.bounds.width, self._row_height)
            selected = index == self._selected_index
            if selected:
                fill = self._selected_background
            elif index % 2:
                fill = self._alternate_row_background
            else:
                fill = self._row_background
            row_node = SceneNode(
                key=f"{self.key}:row:{index}",
                kind=SceneNodeKind.RECTANGLE,
                bounds=row_bounds,
                fill=fill,
                z_index=1,
                clip_to_bounds=True,
                hit_testable=False,
            )
            x = self.bounds.x
            row = self._rows[index]
            for column in self._columns:
                width = column.resolved_width
                cell_bounds = Rect(x, y, width, self._row_height)
                cell = SceneNode(
                    key=f"{self.key}:row:{index}:cell:{column.key}",
                    kind=SceneNodeKind.GROUP,
                    bounds=cell_bounds,
                    z_index=2,
                    clip_to_bounds=True,
                    hit_testable=False,
                )
                cell.add(self._text_node(
                    key=f"{self.key}:row:{index}:text:{column.key}",
                    bounds=cell_bounds,
                    text=str(row.get(column.key, "")),
                    color=self._foreground,
                    font_size=self._font_size,
                ))
                row_node.add(cell)
                x += width
            root.add(row_node)

    def _append_column_separators(self, root: SceneNode) -> None:
        x = self.bounds.x
        bottom = self.bounds.y + self.bounds.height
        for column in self._columns[:-1]:
            x += column.resolved_width
            root.add(
                SceneNode(
                    key=f"{self.key}:separator:{column.key}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(x, self.bounds.y, 1.0, max(0.0, bottom - self.bounds.y)),
                    fill=self._grid_line,
                    z_index=4,
                    hit_testable=False,
                )
            )
        header_line_y = min(bottom, self.bounds.y + self._header_height)
        root.add(
            SceneNode(
                key=f"{self.key}:header-separator",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(self.bounds.x, header_line_y, self.bounds.width, 1.0),
                fill=self._grid_line,
                z_index=4,
                hit_testable=False,
            )
        )

    def _text_node(
        self,
        *,
        key: str,
        bounds: Rect,
        text: str,
        color: Color,
        font_size: float,
    ) -> SceneNode:
        width = max(0.0, bounds.width - (2.0 * self._cell_padding))
        line_height = min(bounds.height, font_size * 1.35)
        y = bounds.y + max(0.0, (bounds.height - line_height) * 0.5)
        return SceneNode(
            key=key,
            kind=SceneNodeKind.TEXT,
            bounds=Rect(bounds.x + self._cell_padding, y, width, line_height),
            fill=color,
            text=text,
            font_size=font_size,
            font_family=self._font_family,
            z_index=2,
            hit_testable=False,
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.y is None
        ):
            return
        body_top = self.bounds.y + self._header_height
        if platform_event.y < body_top or platform_event.y >= self.bounds.y + self.bounds.height:
            return
        content_y = platform_event.y - body_top + self._effective_scroll_offset()
        index = int(content_y // self._row_height)
        if 0 <= index < len(self._rows):
            self.select_row(index, ensure_visible=False)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or not self._rows:
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        key_code = platform_event.key_code
        current = self._selected_index
        if key_code == _VK_HOME:
            target = 0
        elif key_code == _VK_END:
            target = len(self._rows) - 1
        elif key_code == _VK_UP:
            target = 0 if current is None else max(0, current - 1)
        elif key_code == _VK_DOWN:
            target = 0 if current is None else min(len(self._rows) - 1, current + 1)
        elif key_code in (_VK_PRIOR, _VK_NEXT):
            page_rows = max(1, int(self._body_height() // self._row_height))
            origin = 0 if current is None else current
            direction = -1 if key_code == _VK_PRIOR else 1
            target = min(len(self._rows) - 1, max(0, origin + (direction * page_rows)))
        else:
            return

        self.select_row(target, ensure_visible=True)
        event.prevent_default()

    def _set_scroll_offset(self, value: float) -> DataGrid:
        normalized = min(max(0.0, float(value)), self._max_scroll_offset())
        if normalized == self._scroll_offset:
            return self
        self._scroll_offset = normalized
        self.invalidate(reason="scroll_offset")
        return self

    def _effective_scroll_offset(self) -> float:
        return min(self._scroll_offset, self._max_scroll_offset())

    def _body_height(self) -> float:
        return max(0.0, self.bounds.height - self._header_height)

    def _max_scroll_offset(self) -> float:
        content_height = len(self._rows) * self._row_height
        return max(0.0, content_height - self._body_height())

    @staticmethod
    def _snapshot_rows(rows: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
        return tuple(dict(row) for row in rows)

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and positive.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized
