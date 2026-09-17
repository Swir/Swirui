"""Retained editable text widgets with routed keyboard and text input."""

from __future__ import annotations

import math
from typing import Any

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
_VK_A = 0x41

_DEFAULT_BACKGROUND = Color.from_hex("#07111C")
_DEFAULT_FOCUSED_BACKGROUND = Color.from_hex("#0B1C2B")
_DEFAULT_DISABLED_BACKGROUND = Color.from_hex("#101820")
_DEFAULT_FOREGROUND = Color.from_hex("#F4FAFF")
_DEFAULT_PLACEHOLDER = Color.from_hex("#8DA8B8")
_DEFAULT_SELECTION = Color.from_hex("#125D83")
_DEFAULT_CARET = Color.from_hex("#62E5FF")


class _TextInputBase(Widget):
    """Shared retained editing model for single-line and multiline text controls."""

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        placeholder: str = "",
        read_only: bool = False,
        max_length: int | None = None,
        background: Color | None = None,
        focused_background: Color | None = None,
        disabled_background: Color | None = None,
        foreground: Color | None = None,
        placeholder_color: Color | None = None,
        selection_color: Color | None = None,
        caret_color: Color | None = None,
        corner_radius: float = 7.0,
        font_size: float = 16.0,
        font_family: str = "Segoe UI",
        padding: float = 10.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
        multiline: bool = False,
        mask_character: str | None = None,
        accessibility_role: AccessibilityRole = AccessibilityRole.TEXT_BOX,
    ) -> None:
        self._multiline = bool(multiline)
        self._mask_character = self._validate_mask_character(mask_character)
        if self._multiline and self._mask_character is not None:
            raise ValueError("multiline password input is not supported.")
        self._max_length = self._validate_max_length(max_length)
        self._value = self._normalize_value(value)
        if self._max_length is not None:
            self._value = self._value[: self._max_length]
        self._placeholder = str(placeholder)
        self._read_only = bool(read_only)
        self._background = background or _DEFAULT_BACKGROUND
        self._focused_background = focused_background or _DEFAULT_FOCUSED_BACKGROUND
        self._disabled_background = disabled_background or _DEFAULT_DISABLED_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._placeholder_color = placeholder_color or _DEFAULT_PLACEHOLDER
        self._selection_color = selection_color or _DEFAULT_SELECTION
        self._caret_color = caret_color or _DEFAULT_CARET
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._caret = len(self._value)
        self._selection_anchor: int | None = None
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=accessibility_role,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self.on("text_input", self._on_text_input)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        normalized = self._normalize_value(value)
        if self._max_length is not None:
            normalized = normalized[: self._max_length]
        if normalized == self._value:
            return
        old_value = self._value
        self._value = normalized
        self._caret = min(self._caret, len(self._value))
        self._selection_anchor = None
        self.invalidate(reason="value")
        self.emit("changed", old_value=old_value, value=self._value, input_event=None)

    @property
    def placeholder(self) -> str:
        return self._placeholder

    @placeholder.setter
    def placeholder(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._placeholder:
            return
        self._placeholder = normalized
        self.invalidate(reason="placeholder")

    @property
    def read_only(self) -> bool:
        return self._read_only

    @read_only.setter
    def read_only(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._read_only:
            return
        self._read_only = normalized
        self.invalidate(reason="read_only")

    @property
    def max_length(self) -> int | None:
        return self._max_length

    @property
    def caret_index(self) -> int:
        return self._caret

    @property
    def selection_start(self) -> int:
        if self._selection_anchor is None:
            return self._caret
        return min(self._selection_anchor, self._caret)

    @property
    def selection_end(self) -> int:
        if self._selection_anchor is None:
            return self._caret
        return max(self._selection_anchor, self._caret)

    @property
    def selected_text(self) -> str:
        return self._value[self.selection_start : self.selection_end]

    @property
    def focused(self) -> bool:
        return self._focused

    def select(self, start: int, end: int) -> None:
        length = len(self._value)
        start_index = max(0, min(int(start), length))
        end_index = max(0, min(int(end), length))
        old = (self._selection_anchor, self._caret)
        self._selection_anchor = None if start_index == end_index else start_index
        self._caret = end_index
        if old != (self._selection_anchor, self._caret):
            self.invalidate(reason="selection")

    def select_all(self) -> None:
        self.select(0, len(self._value))

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._current_background(),
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        content = self._content_bounds()
        if content.width <= 0.0 or content.height <= 0.0:
            return root

        if self._multiline:
            self._build_multiline_content(root, content)
        else:
            self._build_single_line_content(root, content)
        return root

    def _build_single_line_content(self, root: SceneNode, content: Rect) -> None:
        display_value = self._display_value()
        char_width = self._estimated_char_width()
        capacity = max(1, int(content.width / char_width))
        start = 0
        if len(display_value) > capacity:
            start = min(max(0, self._caret - capacity + 1), len(display_value) - capacity)
        visible = display_value[start : start + capacity]
        showing_placeholder = not self._value and bool(self._placeholder)
        if showing_placeholder:
            visible = self._placeholder[:capacity]
            start = 0

        line_height = min(content.height, self._line_height())
        text_bounds = Rect(content.x, content.y, content.width, line_height)
        if visible:
            root.add(
                SceneNode(
                    key=f"{self.key}:text",
                    kind=SceneNodeKind.TEXT,
                    bounds=text_bounds,
                    z_index=1,
                    fill=self._placeholder_color if showing_placeholder else self._foreground,
                    text=visible,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        if not showing_placeholder:
            selection_start = max(self.selection_start, start)
            selection_end = min(self.selection_end, start + capacity)
            if selection_end > selection_start:
                x = content.x + ((selection_start - start) * char_width)
                width = max(1.0, (selection_end - selection_start) * char_width)
                root.add(
                    SceneNode(
                        key=f"{self.key}:selection",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(x, content.y, min(width, content.right - x), line_height),
                        z_index=0,
                        fill=self._selection_color,
                        hit_testable=False,
                    )
                )

        if self._focused and self.enabled:
            caret_column = max(0, min(self._caret - start, capacity))
            caret_x = min(content.right - 1.0, content.x + (caret_column * char_width))
            root.add(
                SceneNode(
                    key=f"{self.key}:caret",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(caret_x, content.y, 1.5, line_height),
                    z_index=2,
                    fill=self._caret_color,
                    hit_testable=False,
                )
            )

    def _build_multiline_content(self, root: SceneNode, content: Rect) -> None:
        showing_placeholder = not self._value and bool(self._placeholder)
        rendered = self._placeholder if showing_placeholder else self._display_value()
        line_height = self._line_height()
        visible_lines = max(1, int(content.height / line_height))
        start_line = 0 if showing_placeholder else self._multiline_view_start(visible_lines)
        lines = rendered.split("\n")
        visible = "\n".join(lines[start_line : start_line + visible_lines])
        if visible:
            root.add(
                SceneNode(
                    key=f"{self.key}:text",
                    kind=SceneNodeKind.TEXT,
                    bounds=content,
                    z_index=1,
                    fill=self._placeholder_color if showing_placeholder else self._foreground,
                    text=visible,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        if not showing_placeholder and self.selection_start != self.selection_end:
            self._add_multiline_selection(
                root,
                content,
                start_line=start_line,
                visible_lines=visible_lines,
            )

        if not self._focused or not self.enabled:
            return

        line_starts = self._line_starts()
        caret_line = self._line_index_for_position(self._caret, line_starts)
        if caret_line < start_line or caret_line >= start_line + visible_lines:
            return
        column = self._caret - line_starts[caret_line]
        y = content.y + ((caret_line - start_line) * line_height)
        x = min(content.right - 1.0, content.x + (column * self._estimated_char_width()))
        root.add(
            SceneNode(
                key=f"{self.key}:caret",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(x, y, 1.5, min(line_height, content.bottom - y)),
                z_index=2,
                fill=self._caret_color,
                hit_testable=False,
            )
        )

    def _add_multiline_selection(
        self,
        root: SceneNode,
        content: Rect,
        *,
        start_line: int,
        visible_lines: int,
    ) -> None:
        line_starts = self._line_starts()
        char_width = self._estimated_char_width()
        line_height = self._line_height()
        selection_start = self.selection_start
        selection_end = self.selection_end
        stop_line = min(len(line_starts), start_line + visible_lines)
        for line_index in range(start_line, stop_line):
            line_start = line_starts[line_index]
            line_end = self._line_end(line_start)
            segment_start = max(selection_start, line_start)
            segment_end = min(selection_end, line_end)
            if segment_end <= segment_start:
                # Include a selected newline as a thin visible end-of-line marker.
                if not (
                    selection_start <= line_end < selection_end
                    and line_end < len(self._value)
                    and self._value[line_end] == "\n"
                ):
                    continue
                segment_start = line_end
                segment_end = line_end
            x = content.x + ((segment_start - line_start) * char_width)
            width = max(char_width * 0.45, (segment_end - segment_start) * char_width)
            width = min(width, max(0.0, content.right - x))
            if width <= 0.0:
                continue
            y = content.y + ((line_index - start_line) * line_height)
            root.add(
                SceneNode(
                    key=f"{self.key}:selection:{line_index}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(x, y, width, min(line_height, content.bottom - y)),
                    z_index=0,
                    fill=self._selection_color,
                    hit_testable=False,
                )
            )

    def _multiline_view_start(self, visible_lines: int) -> int:
        if not self._focused:
            return 0
        line_starts = self._line_starts()
        caret_line = self._line_index_for_position(self._caret, line_starts)
        return max(0, min(caret_line - visible_lines + 1, len(line_starts) - visible_lines))

    def _current_background(self) -> Color:
        if not self.enabled:
            return self._disabled_background
        if self._focused:
            return self._focused_background
        return self._background

    def _content_bounds(self) -> Rect:
        width = max(0.0, self.bounds.width - (2.0 * self._padding))
        height = max(0.0, self.bounds.height - (2.0 * self._padding))
        if self._multiline:
            return Rect(self.bounds.x + self._padding, self.bounds.y + self._padding, width, height)
        line_height = min(height, self._line_height())
        y = self.bounds.y + max(0.0, (self.bounds.height - line_height) * 0.5)
        return Rect(self.bounds.x + self._padding, y, width, line_height)

    def _display_value(self) -> str:
        if self._mask_character is None:
            return self._value
        return self._mask_character * len(self._value)

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
        ):
            return
        index = self._index_from_point(platform_event.x, platform_event.y)
        self._move_caret(index, extend=platform_event.shift)

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or platform_event.key_code is None:
            return
        key = platform_event.key_code
        if (
            platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
            and key == _VK_A
        ):
            self.select_all()
            event.prevent_default()
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        if key == _VK_LEFT:
            self._move_horizontal(-1, extend=platform_event.shift)
        elif key == _VK_RIGHT:
            self._move_horizontal(1, extend=platform_event.shift)
        elif key == _VK_HOME:
            self._move_caret(self._line_boundary(start=True), extend=platform_event.shift)
        elif key == _VK_END:
            self._move_caret(self._line_boundary(start=False), extend=platform_event.shift)
        elif self._multiline and key == _VK_UP:
            self._move_vertical(-1, extend=platform_event.shift)
        elif self._multiline and key == _VK_DOWN:
            self._move_vertical(1, extend=platform_event.shift)
        elif key == _VK_BACK:
            if not self._read_only:
                self._delete_backward(event)
        elif key == _VK_DELETE:
            if not self._read_only:
                self._delete_forward(event)
        elif key == _VK_RETURN and not self._multiline:
            self.emit("submitted", value=self._value, input_event=event)
        else:
            return
        event.prevent_default()

    def _on_text_input(self, event: Event) -> None:
        if not self.enabled or self._read_only:
            return
        platform_event = self._platform_event(event, PlatformEventKind.TEXT_INPUT)
        if platform_event is None or platform_event.text is None:
            return
        text = self._normalize_inserted_text(platform_event.text)
        if not text:
            return
        self._replace_selection(text, input_event=event)
        event.prevent_default()

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        if self._focused:
            self._focused = False
            self._selection_anchor = None
            self.invalidate(reason="focus_lost")

    def _replace_selection(self, text: str, *, input_event: Event) -> None:
        start = self.selection_start
        end = self.selection_end
        available = None
        if self._max_length is not None:
            retained_length = len(self._value) - (end - start)
            available = max(0, self._max_length - retained_length)
        inserted = text if available is None else text[:available]
        if not inserted and start == end:
            return
        old_value = self._value
        self._value = f"{self._value[:start]}{inserted}{self._value[end:]}"
        self._caret = start + len(inserted)
        self._selection_anchor = None
        if self._value != old_value:
            self.invalidate(reason="value")
            self.emit(
                "changed",
                old_value=old_value,
                value=self._value,
                input_event=input_event,
            )

    def _delete_backward(self, input_event: Event) -> None:
        if self.selection_start != self.selection_end:
            self._replace_selection("", input_event=input_event)
            return
        if self._caret <= 0:
            return
        self.select(self._caret - 1, self._caret)
        self._replace_selection("", input_event=input_event)

    def _delete_forward(self, input_event: Event) -> None:
        if self.selection_start != self.selection_end:
            self._replace_selection("", input_event=input_event)
            return
        if self._caret >= len(self._value):
            return
        self.select(self._caret, self._caret + 1)
        self._replace_selection("", input_event=input_event)

    def _move_horizontal(self, delta: int, *, extend: bool) -> None:
        if not extend and self.selection_start != self.selection_end:
            target = self.selection_start if delta < 0 else self.selection_end
        else:
            target = self._caret + delta
        self._move_caret(target, extend=extend)

    def _move_vertical(self, delta: int, *, extend: bool) -> None:
        line_starts = self._line_starts()
        current_line = self._line_index_for_position(self._caret, line_starts)
        column = self._caret - line_starts[current_line]
        target_line = max(0, min(current_line + delta, len(line_starts) - 1))
        target_start = line_starts[target_line]
        target_end = self._line_end(target_start)
        self._move_caret(min(target_start + column, target_end), extend=extend)

    def _move_caret(self, index: int, *, extend: bool) -> None:
        target = max(0, min(int(index), len(self._value)))
        old = (self._selection_anchor, self._caret)
        if extend:
            if self._selection_anchor is None:
                self._selection_anchor = self._caret
        else:
            self._selection_anchor = None
        self._caret = target
        if self._selection_anchor == self._caret:
            self._selection_anchor = None
        if old != (self._selection_anchor, self._caret):
            self.invalidate(reason="selection")

    def _line_boundary(self, *, start: bool) -> int:
        if not self._multiline:
            return 0 if start else len(self._value)
        line_start = self._value.rfind("\n", 0, self._caret) + 1
        if start:
            return line_start
        return self._line_end(line_start)

    def _line_starts(self) -> list[int]:
        starts = [0]
        starts.extend(index + 1 for index, char in enumerate(self._value) if char == "\n")
        return starts

    @staticmethod
    def _line_index_for_position(position: int, line_starts: list[int]) -> int:
        return max(
            0,
            next(
                (index - 1 for index, start in enumerate(line_starts) if start > position),
                len(line_starts) - 1,
            ),
        )

    def _line_end(self, line_start: int) -> int:
        newline = self._value.find("\n", line_start)
        return len(self._value) if newline < 0 else newline

    def _index_from_point(self, x: float, y: float) -> int:
        content = self._content_bounds()
        char_width = self._estimated_char_width()
        if not self._multiline:
            display_value = self._display_value()
            capacity = max(1, int(content.width / char_width))
            start = 0
            if len(display_value) > capacity:
                start = min(max(0, self._caret - capacity + 1), len(display_value) - capacity)
            column = round((x - content.x) / char_width)
            return max(start, min(start + column, min(len(self._value), start + capacity)))

        line_starts = self._line_starts()
        visible_lines = max(1, int(content.height / self._line_height()))
        view_start = self._multiline_view_start(visible_lines)
        line = view_start + int(max(0.0, y - content.y) / self._line_height())
        line = max(0, min(line, len(line_starts) - 1))
        start = line_starts[line]
        end = self._line_end(start)
        column = round((x - content.x) / char_width)
        return max(start, min(start + column, end))

    def _normalize_value(self, value: str) -> str:
        normalized = str(value).replace("\r\n", "\n").replace("\r", "\n")
        if self._multiline:
            return normalized
        return normalized.replace("\n", "")

    def _normalize_inserted_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        filtered = "".join(
            char for char in normalized if char >= " " or (self._multiline and char == "\n")
        )
        if self._multiline:
            return filtered
        return filtered.replace("\n", "")

    def _estimated_char_width(self) -> float:
        return max(1.0, self._font_size * 0.58)

    def _line_height(self) -> float:
        return self._font_size * 1.3

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
            raise ValueError(f"{name} must be finite and greater than zero.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized

    @staticmethod
    def _validate_font_family(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("font_family cannot be empty.")
        return normalized

    @staticmethod
    def _validate_max_length(value: int | None) -> int | None:
        if value is None:
            return None
        normalized = int(value)
        if normalized < 0:
            raise ValueError("max_length must be non-negative or None.")
        return normalized

    @staticmethod
    def _validate_mask_character(value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) != 1 or value < " ":
            raise ValueError("mask_character must contain exactly one visible character.")
        return value


class Input(_TextInputBase):
    """Single-line editable retained text input."""

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        placeholder: str = "",
        read_only: bool = False,
        max_length: int | None = None,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            value,
            bounds=bounds,
            key=key,
            placeholder=placeholder,
            read_only=read_only,
            max_length=max_length,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            multiline=False,
            **kwargs,
        )


class PasswordInput(_TextInputBase):
    """Single-line input that renders a mask instead of the stored value."""

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        placeholder: str = "",
        read_only: bool = False,
        max_length: int | None = None,
        mask_character: str = "•",
        accessible_name: str | None = None,
        accessible_description: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            value,
            bounds=bounds,
            key=key,
            placeholder=placeholder,
            read_only=read_only,
            max_length=max_length,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            multiline=False,
            mask_character=mask_character,
            accessibility_role=AccessibilityRole.PASSWORD_BOX,
            **kwargs,
        )


class TextArea(_TextInputBase):
    """Multiline retained text editor using the shaped-text GPU path."""

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        placeholder: str = "",
        read_only: bool = False,
        max_length: int | None = None,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            value,
            bounds=bounds,
            key=key,
            placeholder=placeholder,
            read_only=read_only,
            max_length=max_length,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            multiline=True,
            **kwargs,
        )
