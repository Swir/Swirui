"""Retained source-code editor with bounded history and syntax highlighting."""

from __future__ import annotations

import io
import keyword
import math
import token as token_module
import tokenize
from dataclasses import dataclass
from typing import Any, Mapping

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
_DEFAULT_SYNTAX_COLORS = {
    "keyword": Color.from_hex("#62E5FF"),
    "definition": Color.from_hex("#82AAFF"),
    "string": Color.from_hex("#A6E3A1"),
    "number": Color.from_hex("#F5C76E"),
    "comment": Color.from_hex("#718797"),
    "decorator": Color.from_hex("#C792EA"),
    "operator": Color.from_hex("#89DDFF"),
    "literal": Color.from_hex("#FF8CCF"),
    "key": Color.from_hex("#7FDBFF"),
}
_PYTHON_LITERALS = frozenset({"True", "False", "None", "NotImplemented", "Ellipsis"})
_HIGHLIGHTED_OPERATORS = frozenset(
    {
        "+",
        "-",
        "*",
        "/",
        "//",
        "%",
        "**",
        "=",
        "==",
        "!=",
        "<",
        ">",
        "<=",
        ">=",
        "->",
        ":=",
        "|",
        "&",
        "^",
        "~",
        "<<",
        ">>",
        "+=",
        "-=",
        "*=",
        "/=",
        "//=",
        "%=",
        "**=",
        "|=",
        "&=",
        "^=",
        "<<=",
        ">>=",
    }
)
_PYTHON_STRING_TOKENS = {token_module.STRING}
for _token_name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    _token_value = getattr(token_module, _token_name, None)
    if isinstance(_token_value, int):
        _PYTHON_STRING_TOKENS.add(_token_value)

_MAX_HIGHLIGHT_NODES_PER_FRAME = 512


@dataclass(frozen=True, slots=True)
class _EditorSnapshot:
    value: str
    caret: int
    selection_anchor: int | None
    scroll_offset: float


@dataclass(frozen=True, slots=True)
class _SyntaxSpan:
    start: int
    end: int
    kind: str


class CodeEditor(TextArea):
    """Python-first retained code editor built on SwirUI's shaped-text path.

    Editor mechanics stay application-neutral while optional syntax highlighting
    provides built-in Python and JSON lexers. Highlighting is cached per source
    value and only materializes retained text overlays for visible rows, keeping
    scene complexity bounded by the viewport rather than document length.
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
        syntax_highlighting: bool = True,
        language: str | None = None,
        syntax_colors: Mapping[str, Color] | None = None,
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
        self._syntax_highlighting = bool(syntax_highlighting)
        self._language = self._normalize_language(language)
        self._syntax_colors = self._validate_syntax_colors(syntax_colors)
        self._syntax_cache_value: str | None = None
        self._syntax_cache_language: str | None = None
        self._syntax_cache: dict[int, tuple[_SyntaxSpan, ...]] = {}
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
    def syntax_highlighting(self) -> bool:
        return self._syntax_highlighting

    @syntax_highlighting.setter
    def syntax_highlighting(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._syntax_highlighting:
            return
        self._syntax_highlighting = normalized
        self._sync_editor_accessibility()
        self.invalidate(reason="syntax_highlighting")

    @property
    def language(self) -> str | None:
        return self._language

    @language.setter
    def language(self, value: str | None) -> None:
        normalized = self._normalize_language(value)
        if normalized == self._language:
            return
        self._language = normalized
        self._clear_syntax_cache()
        self._sync_editor_accessibility()
        self.invalidate(reason="syntax_language")

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

        if self._syntax_highlighting and self._language is not None and self._value:
            self._add_syntax_highlights(
                root,
                content=content,
                first_line=first_line,
                visible_lines=visible_lines,
                line_height=line_height,
            )

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

    def _add_syntax_highlights(
        self,
        root: SceneNode,
        *,
        content: Rect,
        first_line: int,
        visible_lines: int,
        line_height: float,
    ) -> None:
        syntax_lines = self._syntax_lines()
        source_lines = self._value.split("\n")
        char_width = self._estimated_char_width()
        visible_columns = max(1, int(content.width / char_width) + 2)
        stop = min(len(source_lines), first_line + visible_lines)
        node_count = 0

        for line_index in range(first_line, stop):
            line = source_lines[line_index]
            y = content.y + ((line_index - first_line) * line_height)
            for span_index, span in enumerate(syntax_lines.get(line_index, ())):
                if node_count >= _MAX_HIGHLIGHT_NODES_PER_FRAME:
                    return
                if span.start >= visible_columns:
                    break
                span_end = min(span.end, visible_columns, len(line))
                if span_end <= span.start:
                    continue
                text = line[span.start:span_end]
                if not text:
                    continue
                x = content.x + (span.start * char_width)
                if x >= content.right:
                    continue
                width = min(
                    max(char_width * 0.45, len(text) * char_width),
                    max(0.0, content.right - x),
                )
                if width <= 0.0:
                    continue
                root.add(
                    SceneNode(
                        key=(
                            f"{self.key}:syntax:{line_index + 1}:"
                            f"{span_index}:{span.kind}"
                        ),
                        kind=SceneNodeKind.TEXT,
                        bounds=Rect(
                            x,
                            y,
                            width,
                            min(line_height, max(0.0, content.bottom - y)),
                        ),
                        z_index=1,
                        fill=self._syntax_colors[span.kind],
                        text=text,
                        font_size=self._font_size,
                        font_family=self._font_family,
                        hit_testable=False,
                    )
                )
                node_count += 1

    def _syntax_lines(self) -> dict[int, tuple[_SyntaxSpan, ...]]:
        if (
            self._syntax_cache_value == self._value
            and self._syntax_cache_language == self._language
        ):
            return self._syntax_cache

        if self._language == "python":
            parsed = self._parse_python_syntax(self._value)
        elif self._language == "json":
            parsed = self._parse_json_syntax(self._value)
        else:
            parsed = {}
        self._syntax_cache_value = self._value
        self._syntax_cache_language = self._language
        self._syntax_cache = parsed
        return parsed

    @classmethod
    def _parse_python_syntax(cls, source: str) -> dict[int, tuple[_SyntaxSpan, ...]]:
        lines = source.split("\n")
        spans: dict[int, list[_SyntaxSpan]] = {}
        expect_definition = False
        expect_decorator = False

        try:
            stream = tokenize.generate_tokens(io.StringIO(source).readline)
            for info in stream:
                kind: str | None = None
                if info.type == token_module.NAME:
                    if expect_definition:
                        kind = "definition"
                        expect_definition = False
                    elif expect_decorator:
                        kind = "decorator"
                        expect_decorator = False
                    elif info.string in _PYTHON_LITERALS:
                        kind = "literal"
                    elif cls._is_python_keyword(info.string):
                        kind = "keyword"
                        expect_definition = info.string in {"def", "class"}
                elif info.type in _PYTHON_STRING_TOKENS:
                    kind = "string"
                elif info.type == token_module.NUMBER:
                    kind = "number"
                elif info.type == tokenize.COMMENT:
                    kind = "comment"
                elif info.type == token_module.OP:
                    if info.string == "@":
                        kind = "decorator"
                        expect_decorator = True
                    elif info.string in _HIGHLIGHTED_OPERATORS:
                        kind = "operator"

                if kind is not None:
                    cls._append_multiline_span(
                        spans,
                        lines,
                        info.start,
                        info.end,
                        kind,
                    )
        except (tokenize.TokenError, IndentationError):
            # Editing frequently produces temporarily incomplete source. Keep all
            # successfully emitted tokens instead of turning that into an error.
            pass

        return {line: tuple(items) for line, items in spans.items()}

    @classmethod
    def _parse_json_syntax(cls, source: str) -> dict[int, tuple[_SyntaxSpan, ...]]:
        parsed: dict[int, tuple[_SyntaxSpan, ...]] = {}
        for line_index, line in enumerate(source.split("\n")):
            spans: list[_SyntaxSpan] = []
            index = 0
            while index < len(line):
                character = line[index]
                if character in {'"', "'"}:
                    quote = character
                    end = index + 1
                    escaped = False
                    while end < len(line):
                        current = line[end]
                        if current == quote and not escaped:
                            end += 1
                            break
                        if current == "\\" and not escaped:
                            escaped = True
                        else:
                            escaped = False
                        end += 1
                    probe = end
                    while probe < len(line) and line[probe].isspace():
                        probe += 1
                    kind = "key" if probe < len(line) and line[probe] == ":" else "string"
                    spans.append(_SyntaxSpan(index, end, kind))
                    index = end
                    continue

                if character.isdigit() or (
                    character == "-"
                    and index + 1 < len(line)
                    and line[index + 1].isdigit()
                ):
                    end = index + 1
                    while end < len(line) and line[end] in "0123456789+-.eE":
                        end += 1
                    spans.append(_SyntaxSpan(index, end, "number"))
                    index = end
                    continue

                literal = next(
                    (
                        value
                        for value in ("true", "false", "null")
                        if line.startswith(value, index)
                        and cls._json_word_boundary(line, index + len(value))
                    ),
                    None,
                )
                if literal is not None:
                    spans.append(_SyntaxSpan(index, index + len(literal), "literal"))
                    index += len(literal)
                    continue

                index += 1

            if spans:
                parsed[line_index] = tuple(spans)
        return parsed

    @staticmethod
    def _append_multiline_span(
        spans: dict[int, list[_SyntaxSpan]],
        lines: list[str],
        start: tuple[int, int],
        end: tuple[int, int],
        kind: str,
    ) -> None:
        start_row, start_column = start
        end_row, end_column = end
        first = max(0, start_row - 1)
        last = min(len(lines) - 1, end_row - 1)
        for line_index in range(first, last + 1):
            span_start = start_column if line_index == first else 0
            span_end = end_column if line_index == last else len(lines[line_index])
            span_start = max(0, min(span_start, len(lines[line_index])))
            span_end = max(span_start, min(span_end, len(lines[line_index])))
            if span_end > span_start:
                spans.setdefault(line_index, []).append(
                    _SyntaxSpan(span_start, span_end, kind)
                )

    @staticmethod
    def _is_python_keyword(value: str) -> bool:
        if keyword.iskeyword(value):
            return True
        is_softkeyword = getattr(keyword, "issoftkeyword", None)
        return bool(is_softkeyword is not None and is_softkeyword(value))

    @staticmethod
    def _json_word_boundary(line: str, index: int) -> bool:
        return index >= len(line) or not (line[index].isalnum() or line[index] == "_")

    def _clear_syntax_cache(self) -> None:
        self._syntax_cache_value = None
        self._syntax_cache_language = None
        self._syntax_cache = {}

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
        syntax = ""
        if self._syntax_highlighting and self._language is not None:
            syntax = f"; syntax {self._language}"
        self.accessible_value_text = (
            f"{self.line_count} lines; caret line {caret_line + 1}, column {column + 1}; "
            f"visible lines {visible_start}-{visible_end}{syntax}"
        )

    @staticmethod
    def _normalize_language(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"", "plain", "text", "none"}:
            return None
        aliases = {
            "py": "python",
            "python": "python",
            "json": "json",
        }
        try:
            return aliases[normalized]
        except KeyError as exc:
            raise ValueError(
                "language must be one of: python, py, json, plain, text, none."
            ) from exc

    @staticmethod
    def _validate_syntax_colors(
        value: Mapping[str, Color] | None,
    ) -> dict[str, Color]:
        colors = dict(_DEFAULT_SYNTAX_COLORS)
        if value is None:
            return colors
        for kind, color in value.items():
            if kind not in colors:
                raise ValueError(f"unknown syntax color kind: {kind!r}")
            if not isinstance(color, Color):
                raise TypeError("syntax color values must be Color instances.")
            colors[kind] = color
        return colors

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
