"""Retained terminal surface with scrollback, command history and ANSI colors."""

from __future__ import annotations

import re
from dataclasses import dataclass

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_BACK = 0x08
_VK_RETURN = 0x0D
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_END = 0x23
_VK_DELETE = 0x2E

_DEFAULT_BACKGROUND = Color.from_hex("#071019")
_DEFAULT_FOREGROUND = Color.from_hex("#D7E2EA")
_DEFAULT_PROMPT = Color.from_hex("#62E5FF")
_DEFAULT_CARET = Color.from_hex("#62E5FF")

_ANSI_SGR = re.compile(r"\x1b\[([0-9;]*)m")
_ANSI_COLORS = {
    30: Color.from_hex("#0D1117"),
    31: Color.from_hex("#FF7B72"),
    32: Color.from_hex("#7EE787"),
    33: Color.from_hex("#D29922"),
    34: Color.from_hex("#58A6FF"),
    35: Color.from_hex("#BC8CFF"),
    36: Color.from_hex("#39C5CF"),
    37: Color.from_hex("#C9D1D9"),
    90: Color.from_hex("#6E7681"),
    91: Color.from_hex("#FFA198"),
    92: Color.from_hex("#A7F3B5"),
    93: Color.from_hex("#E3B341"),
    94: Color.from_hex("#79C0FF"),
    95: Color.from_hex("#D2A8FF"),
    96: Color.from_hex("#56D4DD"),
    97: Color.from_hex("#F0F6FC"),
}


@dataclass(frozen=True, slots=True)
class _TerminalSpan:
    text: str
    color: Color


class Terminal(Widget):
    """Retained terminal surface that delegates command execution to the application.

    ``Terminal`` never launches a shell by itself. Applications subscribe to the
    ``submitted`` event, execute or interpret the command according to their own
    policy, then append output with :meth:`write` or :meth:`writeln`.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        prompt: str = "> ",
        max_lines: int = 2000,
        history_limit: int = 200,
        echo_commands: bool = True,
        background: Color | None = None,
        foreground: Color | None = None,
        prompt_color: Color | None = None,
        caret_color: Color | None = None,
        font_size: float = 15.0,
        font_family: str = "Cascadia Mono",
        padding: float = 10.0,
        corner_radius: float = 7.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = "Terminal",
        accessible_description: str | None = None,
    ) -> None:
        self._prompt = str(prompt)
        self._max_lines = self._validate_limit(max_lines, "max_lines")
        self._history_limit = self._validate_limit(history_limit, "history_limit")
        self._echo_commands = bool(echo_commands)
        self._background = background or _DEFAULT_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._prompt_color = prompt_color or _DEFAULT_PROMPT
        self._caret_color = caret_color or _DEFAULT_CARET
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._lines: list[list[_TerminalSpan]] = [[]]
        self._ansi_color = self._foreground
        self._ansi_pending = ""
        self._input = ""
        self._caret = 0
        self._focused = False
        self._history: list[str] = []
        self._history_index: int | None = None
        self._history_draft = ""
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.TEXT_BOX,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self.on("text_input", self._on_text_input)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self._sync_accessibility()

    @property
    def prompt(self) -> str:
        return self._prompt

    @prompt.setter
    def prompt(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._prompt:
            return
        self._prompt = normalized
        self._sync_accessibility()
        self.invalidate(reason="prompt")

    @property
    def input_text(self) -> str:
        return self._input

    @input_text.setter
    def input_text(self, value: str) -> None:
        normalized = self._normalize_input(value)
        if normalized == self._input:
            return
        old_value = self._input
        self._input = normalized
        self._caret = len(self._input)
        self._reset_history_navigation()
        self._sync_accessibility()
        self.invalidate(reason="input")
        self.emit("changed", old_value=old_value, value=self._input, input_event=None)

    @property
    def caret_index(self) -> int:
        return self._caret

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self._plain_line(line) for line in self._display_lines())

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    @property
    def max_lines(self) -> int:
        return self._max_lines

    @property
    def focused(self) -> bool:
        return self._focused

    def write(self, text: object) -> Terminal:
        """Append output while preserving a bounded retained scrollback buffer."""

        data = f"{self._ansi_pending}{text}"
        self._ansi_pending = ""
        cursor = 0
        while cursor < len(data):
            escape = data.find("\x1b[", cursor)
            if escape < 0:
                self._append_plain_output(data[cursor:])
                break
            if escape > cursor:
                self._append_plain_output(data[cursor:escape])
            match = _ANSI_SGR.match(data, escape)
            if match is None:
                if "m" not in data[escape:]:
                    self._ansi_pending = data[escape:]
                    break
                cursor = escape + 1
                continue
            self._apply_sgr(match.group(1))
            cursor = match.end()
        self._trim_scrollback()
        self._sync_accessibility()
        self.invalidate(reason="terminal_output")
        return self

    def writeln(self, text: object = "") -> Terminal:
        """Append output followed by a newline."""

        return self.write(f"{text}\n")

    def clear_buffer(self) -> Terminal:
        """Clear terminal scrollback without shadowing ``Component.clear``."""

        self._lines = [[]]
        self._ansi_color = self._foreground
        self._ansi_pending = ""
        self._sync_accessibility()
        self.invalidate(reason="terminal_clear_buffer")
        return self

    def submit(self, command: str | None = None, *, input_event: Event | None = None) -> Terminal:
        """Submit the current command and emit ``submitted`` for application handling."""

        value = self._input if command is None else self._normalize_input(command)
        if self._echo_commands:
            self.writeln(f"{self._prompt}{value}")
        if value and (not self._history or self._history[-1] != value):
            self._history.append(value)
            if len(self._history) > self._history_limit:
                del self._history[: len(self._history) - self._history_limit]
        old_value = self._input
        self._input = ""
        self._caret = 0
        self._reset_history_navigation()
        self._sync_accessibility()
        self.invalidate(reason="terminal_submit")
        if old_value:
            self.emit("changed", old_value=old_value, value="", input_event=input_event)
        self.emit("submitted", command=value, value=value, input_event=input_event)
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
        content = self._content_bounds()
        if content.width <= 0.0 or content.height <= 0.0:
            return root

        line_height = self._line_height()
        total_rows = max(1, int(content.height / line_height))
        output_rows = max(0, total_rows - 1)
        char_width = self._estimated_char_width()
        capacity = max(1, int(content.width / char_width))
        display_lines = self._display_lines()
        visible_start = max(0, len(display_lines) - output_rows)
        visible_lines = display_lines[visible_start:] if output_rows else []

        for row, line in enumerate(visible_lines):
            y = content.y + (row * line_height)
            self._add_output_line(
                root,
                line,
                line_index=visible_start + row,
                y=y,
                content=content,
                capacity=capacity,
                char_width=char_width,
                line_height=line_height,
            )

        input_y = content.y + (output_rows * line_height)
        self._add_input_line(
            root,
            y=input_y,
            content=content,
            capacity=capacity,
            char_width=char_width,
            line_height=line_height,
        )
        return root

    def _add_output_line(
        self,
        root: SceneNode,
        line: list[_TerminalSpan],
        *,
        line_index: int,
        y: float,
        content: Rect,
        capacity: int,
        char_width: float,
        line_height: float,
    ) -> None:
        remaining = capacity
        column = 0
        for span_index, span in enumerate(line):
            if remaining <= 0:
                break
            visible = span.text[:remaining]
            if not visible:
                continue
            x = content.x + (column * char_width)
            root.add(
                SceneNode(
                    key=f"{self.key}:line:{line_index}:span:{span_index}",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(x, y, max(0.0, content.right - x), line_height),
                    z_index=1,
                    fill=span.color,
                    text=visible,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
            column += len(visible)
            remaining -= len(visible)

    def _add_input_line(
        self,
        root: SceneNode,
        *,
        y: float,
        content: Rect,
        capacity: int,
        char_width: float,
        line_height: float,
    ) -> None:
        full = f"{self._prompt}{self._input}"
        caret_column = len(self._prompt) + self._caret
        start = max(0, caret_column - capacity + 1) if len(full) > capacity else 0
        visible = full[start : start + capacity]
        prompt_visible_start = max(start, 0)
        prompt_visible_end = min(start + len(visible), len(self._prompt))

        if prompt_visible_end > prompt_visible_start:
            prompt_text = self._prompt[prompt_visible_start:prompt_visible_end]
            root.add(
                SceneNode(
                    key=f"{self.key}:prompt",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(content.x, y, content.width, line_height),
                    z_index=1,
                    fill=self._prompt_color,
                    text=prompt_text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        input_start = max(start, len(self._prompt))
        input_end = min(start + len(visible), len(full))
        if input_end > input_start:
            text = full[input_start:input_end]
            x = content.x + ((input_start - start) * char_width)
            root.add(
                SceneNode(
                    key=f"{self.key}:input",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(x, y, max(0.0, content.right - x), line_height),
                    z_index=1,
                    fill=self._foreground,
                    text=text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        if self._focused and self.enabled:
            visible_caret = max(0, min(caret_column - start, capacity))
            x = min(content.right - 1.5, content.x + (visible_caret * char_width))
            root.add(
                SceneNode(
                    key=f"{self.key}:caret",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(x, y, 1.5, line_height),
                    z_index=2,
                    fill=self._caret_color,
                    hit_testable=False,
                )
            )

    def _append_plain_output(self, text: str) -> None:
        for char in text.replace("\r\n", "\n"):
            if char == "\n":
                self._lines.append([])
            elif char == "\r":
                self._lines[-1] = []
            elif char == "\b":
                self._erase_output_character()
            elif char == "\t":
                self._append_span("    ")
            elif ord(char) >= 0x20:
                self._append_span(char)

    def _append_span(self, text: str) -> None:
        if not text:
            return
        line = self._lines[-1]
        if line and line[-1].color == self._ansi_color:
            previous = line[-1]
            line[-1] = _TerminalSpan(previous.text + text, previous.color)
        else:
            line.append(_TerminalSpan(text, self._ansi_color))

    def _erase_output_character(self) -> None:
        line = self._lines[-1]
        if not line:
            return
        previous = line[-1]
        shortened = previous.text[:-1]
        if shortened:
            line[-1] = _TerminalSpan(shortened, previous.color)
        else:
            line.pop()

    def _apply_sgr(self, parameters: str) -> None:
        codes = [0] if not parameters else [
            int(value) if value else 0 for value in parameters.split(";")
        ]
        for code in codes:
            if code in (0, 39):
                self._ansi_color = self._foreground
            elif code in _ANSI_COLORS:
                self._ansi_color = _ANSI_COLORS[code]

    def _trim_scrollback(self) -> None:
        trailing_cursor_line = bool(len(self._lines) > 1 and not self._lines[-1])
        limit = self._max_lines + int(trailing_cursor_line)
        overflow = len(self._lines) - limit
        if overflow > 0:
            del self._lines[:overflow]

    def _display_lines(self) -> list[list[_TerminalSpan]]:
        if len(self._lines) == 1 and not self._lines[0]:
            return []
        if len(self._lines) > 1 and not self._lines[-1]:
            return self._lines[:-1]
        return self._lines

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            self.enabled
            and platform_event is not None
            and platform_event.button is PointerButton.LEFT
        ):
            self._caret = len(self._input)
            self.invalidate(reason="terminal_pointer")

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or platform_event.key_code is None:
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        key = platform_event.key_code
        if key == _VK_RETURN:
            self.submit(input_event=event)
        elif key == _VK_BACK:
            if self._caret <= 0:
                return
            self._replace_input(self._input[: self._caret - 1] + self._input[self._caret :])
            self._caret -= 1
        elif key == _VK_DELETE:
            if self._caret >= len(self._input):
                return
            self._replace_input(self._input[: self._caret] + self._input[self._caret + 1 :])
        elif key == _VK_LEFT:
            self._move_caret(self._caret - 1)
        elif key == _VK_RIGHT:
            self._move_caret(self._caret + 1)
        elif key == _VK_HOME:
            self._move_caret(0)
        elif key == _VK_END:
            self._move_caret(len(self._input))
        elif key == _VK_UP:
            self._history_previous()
        elif key == _VK_DOWN:
            self._history_next()
        else:
            return
        event.prevent_default()

    def _on_text_input(self, event: Event) -> None:
        if not self.enabled:
            return
        platform_event = self._platform_event(event, PlatformEventKind.TEXT_INPUT)
        if platform_event is None or platform_event.text is None:
            return
        text = self._normalize_input(platform_event.text)
        if not text:
            return
        old_value = self._input
        self._input = f"{self._input[: self._caret]}{text}{self._input[self._caret :]}"
        self._caret += len(text)
        self._reset_history_navigation()
        self._sync_accessibility()
        self.invalidate(reason="terminal_input")
        self.emit("changed", old_value=old_value, value=self._input, input_event=event)
        event.prevent_default()

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        if self._focused:
            self._focused = False
            self.invalidate(reason="focus_lost")

    def _replace_input(self, value: str) -> None:
        old_value = self._input
        self._input = value
        self._reset_history_navigation()
        self._sync_accessibility()
        self.invalidate(reason="terminal_input")
        if old_value != self._input:
            self.emit("changed", old_value=old_value, value=self._input, input_event=None)

    def _move_caret(self, value: int) -> None:
        target = max(0, min(int(value), len(self._input)))
        if target != self._caret:
            self._caret = target
            self.invalidate(reason="terminal_caret")

    def _history_previous(self) -> None:
        if not self._history:
            return
        if self._history_index is None:
            self._history_draft = self._input
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._set_history_input()

    def _history_next(self) -> None:
        if self._history_index is None:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._set_history_input()
            return
        draft = self._history_draft
        self._history_index = None
        self._history_draft = ""
        self._input = draft
        self._caret = len(self._input)
        self._sync_accessibility()
        self.invalidate(reason="terminal_history")

    def _set_history_input(self) -> None:
        if self._history_index is None:
            return
        self._input = self._history[self._history_index]
        self._caret = len(self._input)
        self._sync_accessibility()
        self.invalidate(reason="terminal_history")

    def _reset_history_navigation(self) -> None:
        self._history_index = None
        self._history_draft = ""

    def _sync_accessibility(self) -> None:
        recent = [self._plain_line(line) for line in self._display_lines()[-3:]]
        summary = "\n".join((*recent, f"{self._prompt}{self._input}"))
        self.accessible_value_text = summary[-512:]

    def _content_bounds(self) -> Rect:
        width = max(0.0, self.bounds.width - (2.0 * self._padding))
        height = max(0.0, self.bounds.height - (2.0 * self._padding))
        return Rect(
            self.bounds.x + self._padding,
            self.bounds.y + self._padding,
            width,
            height,
        )

    def _line_height(self) -> float:
        return max(1.0, self._font_size * 1.35)

    def _estimated_char_width(self) -> float:
        return max(1.0, self._font_size * 0.61)

    @staticmethod
    def _plain_line(line: list[_TerminalSpan]) -> str:
        return "".join(span.text for span in line)

    @staticmethod
    def _normalize_input(value: object) -> str:
        text = str(value).replace("\r", "").replace("\n", "")
        return "".join(char for char in text if ord(char) >= 0x20 and char != "\x7f")

    @staticmethod
    def _validate_limit(value: int, name: str) -> int:
        normalized = int(value)
        if normalized <= 0:
            raise ValueError(f"{name} must be positive.")
        return normalized

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if normalized <= 0.0:
            raise ValueError(f"{name} must be positive.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if normalized < 0.0:
            raise ValueError(f"{name} cannot be negative.")
        return normalized

    @staticmethod
    def _validate_font_family(value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("font_family cannot be empty.")
        return normalized

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        value = event.data.get("platform_event")
        if not isinstance(value, PlatformEvent) or value.kind is not kind:
            return None
        return value


__all__ = ["Terminal"]
