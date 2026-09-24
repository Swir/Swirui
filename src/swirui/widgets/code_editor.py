"""Retained source-code editor surface with gutter, indentation and bounded history."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from swirui.core import Event
from swirui.platforms import PlatformEventKind
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .input import TextArea
from .scroll_events import routed_scroll_deltas, update_scroll_residual

_VK_TAB = 0x09
_VK_PAGE_UP = 0x21
_VK_PAGE_DOWN = 0x22
_VK_Y = 0x59
_VK_Z = 0x5A

_DEFAULT_GUTTER_BACKGROUND = Color.from_hex("#050D15")
_DEFAULT_GUTTER_FOREGROUND = Color.from_hex("#718797")
_DEFAULT_GUTTER_ACTIVE = Color.from_hex("#62E5FF")
_DEFAULT_GUTTER_SEPARATOR = Color.from_hex("#153247")
_DEFAULT_CURRENT_LINE = Color.from_hex("#0D2233")


@dataclass(frozen=True, slots=True)
class _EditorSnapshot:
    value: str
    caret: int
    selection_anchor: int | None
    scroll_offset: float


class CodeEditor(TextArea):
    """Python-first retained code editor built on SwirUI's shaped-text path.

    This gate intentionally owns editor mechanics only: multiline editing,
    line numbers, current-line presentation, indentation, undo/redo and
    viewport-bounded scrolling. Language-aware syntax highlighting remains a
    separate roadmap deliverable.
    """

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        placeholder: str = "",
        read_only: bool = False,
        max_length: int | None = None,
        tab_size: int = 4,
        insert_spaces: bool = True,
        show_line_numbers: bool = True,
        undo_limit: int = 200,
        gutter_background: Color | None = None,
        gutter_foreground: Color | None = None,
        gutter_active_foreground: Color | None = None,
        gutter_separator: Color | None = None,
        current_line_background: Color | None = None,
        gutter_padding: float = 8.0,
        min_gutter_width: float = 42.0,
        font_size: float = 15.0,
        font_family: str = "Cascadia Mono",
        accessible_name: str | None = "Code editor",
        accessible_description: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._tab_size = self._validate_tab_size(tab_size)
        self._insert_spaces = bool(insert_spaces)
        self._show_line_numbers = bool(show_line_numbers)
        self._undo_limit = self._validate_undo_limit(undo_limit)
        self._gutter_background = gutter_background or _DEFAULT_GUTTER_BACKGROUND
        self._gutter_foreground = gutter_foreground or _DEFAULT_GUTTER_FOREGROUND
        self._gutter_active_foreground = (
            gutter_active_foreground or _DEFAULT_GUTTER_ACTIVE
        )
        self._gutter_separator = gutter_separator or _DEFAULT_GUTTER_SEPARATOR
        self._current_line_background = current_line_background or _DEFAULT_CURRENT_LINE
        self._gutter_padding = self._validate_non_negative(
            gutter_padding, "gutter_padding"
        )
        self._min_gutter_width = self._validate_non_negative(
            min_gutter_width, "min_gutter_width"
        )
        self._scroll_offset = 0.0
        self._undo_stack: list[_EditorSnapshot] = []
        self._redo_stack: list[_EditorSnapshot] = []
        self._history_suspended = False

        super().__init__(
            value,
            bounds=bounds,
            key=key,
            placeholder=placeholder,
            read_only=read_only,
            max_length=max_length,
            font_size=font_size,
            font_family=font_family,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            **kwargs,
        )
        self.on("pointer_scroll", self._on_pointer_scroll)
        self._sync_editor_accessibility()

    @property
    def tab_size(self) -> int:
        return self._tab_size

    @property
    def insert_spaces(self) -> bool:
        return self._insert_spaces

    @property
    def show_line_numbers(self) -> bool:
        return self._show_line_numbers

    @show_line_numbers.setter
    def show_line_numbers(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._show_line_numbers:
            return
        self._show_line_numbers = normalized
        self._clamp_scroll_offset()
        self._sync_editor_accessibility()
        self.invalidate(reason="line_numbers")

    @property
    def line_count(self) -> int:
        return self._value.count("\n") + 1

    @property
    def first_visible_line(self) -> int:
        """Return the first visible line as a one-based line number."""

        return self._first_visible_line_index() + 1

    @property
    def visible_line_range(self) -> tuple[int, int]:
        """Return inclusive one-based visible line numbers."""

        capacity = self._visible_line_capacity()
        start = self._first_visible_line_index(capacity)
        return (start + 1, min(self.line_count, start + capacity))

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def scroll_to_line(self, line_number: int) -> bool:
        """Place a one-based line number at the top when the viewport allows it."""

        requested = max(1, min(int(line_number), self.line_count)) - 1
        capacity = self._visible_line_capacity()
        max_start = max(0, self.line_count - capacity)
        target = min(requested, max_start) * self._line_height()
        changed = not math.isclose(target, self._scroll_offset, abs_tol=1e-9)
        if changed:
            self._scroll_offset = target
            self._sync_editor_accessibility()
            self.invalidate(reason="editor_scroll")
        return changed

    def scroll_lines(self, delta: int) -> bool:
        """Scroll vertically by whole retained text rows."""

        amount = int(delta) * self._line_height()
        return self._scroll_by_dips(amount)

    def undo(self) -> bool:
        """Restore the previous editor text/caret snapshot."""

        if not self._undo_stack or self._read_only:
            return False
        target = self._undo_stack.pop()
        self._redo_stack.append(self._capture_snapshot())
        self._trim_history(self._redo_stack)
        self._restore_snapshot(target, reason="undo")
        return True

    def redo(self) -> bool:
        """Restore the next editor text/caret snapshot."""

        if not self._redo_stack or self._read_only:
            return False
        target = self._redo_stack.pop()
        self._undo_stack.append(self._capture_snapshot())
        self._trim_history(self._undo_stack)
        self._restore_snapshot(target, reason="redo")
        return True

    def build_scene_node(self) -> SceneNode:
        root = super().build_scene_node()
        content = self._content_bounds()
        if content.width <= 0.0 or content.height <= 0.0:
            return root

        line_height = self._line_height()
        visible_lines = self._visible_line_capacity()
        first_line = self._first_visible_line_index(visible_lines)
        line_starts = self._line_starts()
        caret_line = self._line_index_for_position(self._caret, line_starts)

        if first_line <= caret_line < first_line + visible_lines:
            y = content.y + ((caret_line - first_line) * line_height)
            highlight = SceneNode(
                key=f"{self.key}:current-line",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    content.x,
                    y,
                    content.width,
                    min(line_height, max(0.0, content.bottom - y)),
                ),
                z_index=-1,
                fill=self._current_line_background,
                hit_testable=False,
            )
            root.children.insert(0, highlight)

        if self._show_line_numbers:
            self._add_gutter(
                root,
                content=content,
                first_line=first_line,
                visible_lines=visible_lines,
                caret_line=caret_line,
                line_height=line_height,
            )

        self._sync_editor_accessibility()
        return root

    def _add_gutter(
        self,
        root: SceneNode,
        *,
        content: Rect,
        first_line: int,
        visible_lines: int,
        caret_line: int,
        line_height: float,
    ) -> None:
        gutter_right = content.x - self._gutter_padding
        gutter_width = max(0.0, gutter_right - self.bounds.x)
        if gutter_width <= 0.0:
            return

        root.add(
            SceneNode(
                key=f"{self.key}:gutter",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(self.bounds.x, self.bounds.y, gutter_width, self.bounds.height),
                z_index=2,
                fill=self._gutter_background,
                hit_testable=False,
            )
        )
        separator_x = max(self.bounds.x, gutter_right - 1.0)
        root.add(
            SceneNode(
                key=f"{self.key}:gutter-separator",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(separator_x, self.bounds.y, 1.0, self.bounds.height),
                z_index=3,
                fill=self._gutter_separator,
                hit_testable=False,
            )
        )

        char_width = self._estimated_char_width()
        stop = min(self.line_count, first_line + visible_lines)
        for line_index in range(first_line, stop):
            label = str(line_index + 1)
            x = max(
                self.bounds.x + self._gutter_padding,
                gutter_right - self._gutter_padding - (len(label) * char_width),
            )
            y = content.y + ((line_index - first_line) * line_height)
            root.add(
                SceneNode(
                    key=f"{self.key}:line-number:{line_index + 1}",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        x,
                        y,
                        max(0.0, gutter_right - x - self._gutter_padding),
                        min(line_height, max(0.0, content.bottom - y)),
                    ),
                    z_index=4,
                    fill=(
                        self._gutter_active_foreground
                        if line_index == caret_line
                        else self._gutter_foreground
                    ),
                    text=label,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

    def _content_bounds(self) -> Rect:
        content = super()._content_bounds()
        gutter = self._gutter_width() if self._show_line_numbers else 0.0
        return Rect(
            content.x + gutter,
            content.y,
            max(0.0, content.width - gutter),
            content.height,
        )

    def _gutter_width(self) -> float:
        digits = len(str(max(1, self.line_count)))
        natural = (digits * self._estimated_char_width()) + (2.0 * self._gutter_padding)
        return max(self._min_gutter_width, natural)

    def _visible_line_capacity(self) -> int:
        content = self._content_bounds()
        return max(1, int(content.height / self._line_height()))

    def _first_visible_line_index(self, capacity: int | None = None) -> int:
        visible_lines = self._visible_line_capacity() if capacity is None else max(1, capacity)
        max_start = max(0, self.line_count - visible_lines)
        start = int(self._scroll_offset / self._line_height())
        return max(0, min(start, max_start))

    def _multiline_view_start(self, visible_lines: int) -> int:
        self._clamp_scroll_offset(visible_lines)
        return self._first_visible_line_index(visible_lines)

    def _max_scroll_offset(self, visible_lines: int | None = None) -> float:
        capacity = (
            self._visible_line_capacity()
            if visible_lines is None
            else max(1, int(visible_lines))
        )
        return max(0, self.line_count - capacity) * self._line_height()

    def _clamp_scroll_offset(self, visible_lines: int | None = None) -> None:
        self._scroll_offset = min(
            max(0.0, self._scroll_offset),
            self._max_scroll_offset(visible_lines),
        )

    def _scroll_by_dips(self, delta: float) -> bool:
        before = self._scroll_offset
        self._scroll_offset = min(
            max(0.0, before + float(delta)),
            self._max_scroll_offset(),
        )
        changed = not math.isclose(before, self._scroll_offset, abs_tol=1e-9)
        if changed:
            self._sync_editor_accessibility()
            self.invalidate(reason="editor_scroll")
        return changed

    def _ensure_caret_visible(self) -> None:
        capacity = self._visible_line_capacity()
        line_starts = self._line_starts()
        caret_line = self._line_index_for_position(self._caret, line_starts)
        first = self._first_visible_line_index(capacity)
        if caret_line < first:
            self._scroll_offset = caret_line * self._line_height()
        elif caret_line >= first + capacity:
            self._scroll_offset = (
                caret_line - capacity + 1
            ) * self._line_height()
        self._clamp_scroll_offset(capacity)

    def _move_caret(self, index: int, *, extend: bool) -> None:
        super()._move_caret(index, extend=extend)
        self._ensure_caret_visible()
        self._sync_editor_accessibility()

    def _replace_selection(self, text: str, *, input_event: Event) -> None:
        before = self._capture_snapshot()
        old_value = self._value
        super()._replace_selection(text, input_event=input_event)
        if self._value == old_value:
            return
        if not self._history_suspended:
            self._remember_undo(before)
            self._redo_stack.clear()
        self._ensure_caret_visible()
        self._sync_editor_accessibility()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or platform_event.key_code is None:
            return

        key = platform_event.key_code
        command_modifier = (
            platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
        )
        if command_modifier and key == _VK_Z:
            if not self._read_only:
                if platform_event.shift:
                    self.redo()
                else:
                    self.undo()
            event.prevent_default()
            return
        if command_modifier and key == _VK_Y:
            if not self._read_only:
                self.redo()
            event.prevent_default()
            return

        if not platform_event.ctrl and not platform_event.alt and not platform_event.meta:
            if key == _VK_TAB:
                if not self._read_only:
                    if platform_event.shift:
                        self._unindent(event)
                    else:
                        self._indent(event)
                event.prevent_default()
                return
            if key in (_VK_PAGE_UP, _VK_PAGE_DOWN):
                direction = -1 if key == _VK_PAGE_UP else 1
                self._move_page(direction, extend=platform_event.shift)
                event.prevent_default()
                return

        super()._on_key_down(event)

    def _on_pointer_scroll(self, event: Event) -> None:
        if not self.enabled or not self.visible:
            return
        deltas = routed_scroll_deltas(event)
        if deltas is None:
            return
        delta_x, delta_y = deltas
        before = self._scroll_offset
        if delta_y:
            self._scroll_offset = min(
                max(0.0, before + delta_y),
                self._max_scroll_offset(),
            )
        consumed_y = self._scroll_offset - before
        if not math.isclose(consumed_y, 0.0, abs_tol=1e-9):
            self._sync_editor_accessibility()
            self.invalidate(reason="editor_scroll")
        update_scroll_residual(
            event,
            delta_x=delta_x,
            delta_y=delta_y - consumed_y,
            consumed=not math.isclose(consumed_y, 0.0, abs_tol=1e-9),
        )

    def _move_page(self, direction: int, *, extend: bool) -> None:
        line_starts = self._line_starts()
        current_line = self._line_index_for_position(self._caret, line_starts)
        column = self._caret - line_starts[current_line]
        capacity = self._visible_line_capacity()
        target_line = max(
            0,
            min(current_line + (direction * capacity), len(line_starts) - 1),
        )
        target_start = line_starts[target_line]
        target_end = self._line_end(target_start)
        self._move_caret(min(target_start + column, target_end), extend=extend)

    def _indent(self, event: Event) -> None:
        if self.selection_start != self.selection_end:
            self._indent_selected_lines(event)
            return
        if self._insert_spaces:
            line_start = self._value.rfind("\n", 0, self._caret) + 1
            column = self._caret - line_start
            count = self._tab_size - (column % self._tab_size)
            text = " " * count
        else:
            text = "\t"
        self._replace_selection(text, input_event=event)

    def _indent_selected_lines(self, event: Event) -> None:
        start, end = self._selected_line_bounds()
        block = self._value[start:end]
        prefix = (" " * self._tab_size) if self._insert_spaces else "\t"
        replacement = prefix + block.replace("\n", f"\n{prefix}")
        self.select(start, end)
        self._replace_selection(replacement, input_event=event)
        self.select(start, start + len(replacement))

    def _unindent(self, event: Event) -> None:
        if self.selection_start != self.selection_end:
            start, end = self._selected_line_bounds()
            block = self._value[start:end]
            replacement = "\n".join(self._unindent_line(line) for line in block.split("\n"))
            if replacement == block:
                return
            self.select(start, end)
            self._replace_selection(replacement, input_event=event)
            self.select(start, start + len(replacement))
            return

        line_start = self._value.rfind("\n", 0, self._caret) + 1
        line_end = self._line_end(line_start)
        line = self._value[line_start:line_end]
        replacement = self._unindent_line(line)
        removed = len(line) - len(replacement)
        if removed <= 0:
            return
        original_caret = self._caret
        self.select(line_start, line_start + removed)
        self._replace_selection("", input_event=event)
        self._move_caret(max(line_start, original_caret - removed), extend=False)

    def _selected_line_bounds(self) -> tuple[int, int]:
        start = self.selection_start
        end = self.selection_end
        line_start = self._value.rfind("\n", 0, start) + 1
        probe = max(line_start, end - 1)
        newline = self._value.find("\n", probe)
        line_end = len(self._value) if newline < 0 else newline
        return (line_start, line_end)

    def _unindent_line(self, line: str) -> str:
        if line.startswith("\t"):
            return line[1:]
        spaces = len(line) - len(line.lstrip(" "))
        return line[min(spaces, self._tab_size) :]

    def _capture_snapshot(self) -> _EditorSnapshot:
        return _EditorSnapshot(
            value=self._value,
            caret=self._caret,
            selection_anchor=self._selection_anchor,
            scroll_offset=self._scroll_offset,
        )

    def _remember_undo(self, snapshot: _EditorSnapshot) -> None:
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        self._trim_history(self._undo_stack)

    def _trim_history(self, stack: list[_EditorSnapshot]) -> None:
        if len(stack) > self._undo_limit:
            del stack[: len(stack) - self._undo_limit]

    def _restore_snapshot(self, snapshot: _EditorSnapshot, *, reason: str) -> None:
        old_value = self._value
        self._history_suspended = True
        try:
            self._value = snapshot.value
            self._caret = max(0, min(snapshot.caret, len(self._value)))
            anchor = snapshot.selection_anchor
            self._selection_anchor = (
                None
                if anchor is None
                else max(0, min(anchor, len(self._value)))
            )
            self._scroll_offset = snapshot.scroll_offset
            self._clamp_scroll_offset()
        finally:
            self._history_suspended = False
        self._sync_editor_accessibility()
        self.invalidate(reason=reason)
        if old_value != self._value:
            self.emit("changed", old_value=old_value, value=self._value, input_event=None)

    def _sync_editor_accessibility(self) -> None:
        line_starts = self._line_starts()
        caret_line = self._line_index_for_position(self._caret, line_starts)
        column = self._caret - line_starts[caret_line]
        visible_start, visible_end = self.visible_line_range
        self.accessible_value_text = (
            f"{self.line_count} lines; caret line {caret_line + 1}, column {column + 1}; "
            f"visible lines {visible_start}-{visible_end}"
        )

    @staticmethod
    def _validate_tab_size(value: int) -> int:
        normalized = int(value)
        if normalized < 1 or normalized > 16:
            raise ValueError("tab_size must be between 1 and 16.")
        return normalized

    @staticmethod
    def _validate_undo_limit(value: int) -> int:
        normalized = int(value)
        if normalized < 1:
            raise ValueError("undo_limit must be at least 1.")
        return normalized


__all__ = ["CodeEditor"]
