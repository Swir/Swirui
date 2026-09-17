"""Retained editable text controls for SwirUI core widgets."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

# SwirUI currently preserves native key codes in PlatformEvent. These sets cover
# the Win32 virtual-key values plus the X11 keysyms and Cocoa hardware key codes
# emitted by the existing native backends.
_BACKSPACE_KEYS = {0x08, 0xFF08, 51}
_DELETE_KEYS = {0x2E, 0xFFFF, 117}
_LEFT_KEYS = {0x25, 0xFF51, 123}
_RIGHT_KEYS = {0x27, 0xFF53, 124}
_HOME_KEYS = {0x24, 0xFF50, 115}
_END_KEYS = {0x23, 0xFF57, 119}
_RETURN_KEYS = {0x0D, 0xFF0D, 0xFF8D, 36, 76}

_DEFAULT_BACKGROUND = Color.from_hex("#07111C")
_DEFAULT_FOCUSED_BACKGROUND = Color.from_hex("#0A1724")
_DEFAULT_DISABLED_BACKGROUND = Color.from_hex("#18232C")
_DEFAULT_FOREGROUND = Color.from_hex("#F4FAFF")
_DEFAULT_PLACEHOLDER = Color.from_hex("#8DA8B8")
_DEFAULT_CARET = Color.from_hex("#62E5FF")


class Input(Widget):
    """Single-line retained text input using routed native keyboard/text events.

    The widget keeps editing state in Python while rendering through the existing
    shaped-text and rectangle GPU paths. It deliberately consumes TEXT_INPUT for
    character insertion and KEY_DOWN only for editing/navigation commands, which
    avoids keyboard-layout assumptions in the public widget API.
    """

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        placeholder: str = "",
        max_length: int | None = None,
        read_only: bool = False,
        background: Color | None = None,
        focused_background: Color | None = None,
        disabled_background: Color | None = None,
        foreground: Color | None = None,
        placeholder_color: Color | None = None,
        caret_color: Color | None = None,
        corner_radius: float = 7.0,
        font_size: float = 16.0,
        font_family: str = "Segoe UI",
        padding: float = 10.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._max_length = self._validate_max_length(max_length)
        self._value = self._normalize_external_value(str(value))
        if self._max_length is not None:
            self._value = self._value[: self._max_length]
        self._placeholder = str(placeholder)
        self._read_only = bool(read_only)
        self._background = background or _DEFAULT_BACKGROUND
        self._focused_background = focused_background or _DEFAULT_FOCUSED_BACKGROUND
        self._disabled_background = disabled_background or _DEFAULT_DISABLED_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._placeholder_color = placeholder_color or _DEFAULT_PLACEHOLDER
        self._caret_color = caret_color or _DEFAULT_CARET
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._caret_index = len(self._value)
        self._focused = False
        semantic_name = accessible_name or self._placeholder or "Text input"
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.TEXT_BOX,
            accessible_name=semantic_name,
            accessible_description=accessible_description,
        )
        self.on("text_input", self._on_text_input)
        self.on("key_down", self._on_key_down)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        normalized = self._normalize_external_value(str(value))
        if self._max_length is not None:
            normalized = normalized[: self._max_length]
        self._replace_value(normalized, caret=len(normalized), reason="value")

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
    def max_length(self) -> int | None:
        return self._max_length

    @max_length.setter
    def max_length(self, value: int | None) -> None:
        normalized = self._validate_max_length(value)
        if normalized == self._max_length:
            return
        self._max_length = normalized
        if normalized is not None and len(self._value) > normalized:
            self._replace_value(
                self._value[:normalized],
                caret=min(self._caret_index, normalized),
                reason="max_length",
            )
        else:
            self.invalidate(reason="max_length")

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
    def caret_index(self) -> int:
        return self._caret_index

    @caret_index.setter
    def caret_index(self, value: int) -> None:
        normalized = max(0, min(int(value), len(self._value)))
        if normalized == self._caret_index:
            return
        self._caret_index = normalized
        self.invalidate(reason="caret")

    @property
    def focused(self) -> bool:
        return self._focused

    def clear(self) -> None:
        if self._read_only:
            return
        self._replace_value("", caret=0, reason="clear")

    def build_scene_node(self) -> SceneNode:
        node = SceneNode(
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
        self._append_content_nodes(node)
        return node

    def _append_content_nodes(self, node: SceneNode) -> None:
        content = self._content_bounds()
        if content.width <= 0.0 or content.height <= 0.0:
            return

        display, visible_caret = self._visible_single_line()
        if display:
            node.add(
                SceneNode(
                    key=f"{self.key}:text",
                    kind=SceneNodeKind.TEXT,
                    bounds=content,
                    fill=self._foreground,
                    text=display,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        elif self._placeholder:
            node.add(
                SceneNode(
                    key=f"{self.key}:placeholder",
                    kind=SceneNodeKind.TEXT,
                    bounds=content,
                    fill=self._placeholder_color,
                    text=self._placeholder,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        if self._focused and self.enabled and not self._read_only:
            char_width = self._estimated_char_width()
            caret_x = min(
                content.x + content.width - 1.5,
                content.x + (visible_caret * char_width),
            )
            node.add(
                SceneNode(
                    key=f"{self.key}:caret",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(caret_x, content.y, 1.5, content.height),
                    fill=self._caret_color,
                    hit_testable=False,
                    z_index=2,
                )
            )

    def _visible_single_line(self) -> tuple[str, int]:
        display = self._display_value()
        content = self._content_bounds()
        capacity = max(1, int(content.width / self._estimated_char_width()))
        if len(display) <= capacity:
            return display, self._caret_index
        start = max(0, min(self._caret_index - capacity + 1, len(display) - capacity))
        end = min(len(display), start + capacity)
        return display[start:end], self._caret_index - start

    def _display_value(self) -> str:
        return self._value

    def _content_bounds(self) -> Rect:
        width = max(0.0, self.bounds.width - (2.0 * self._padding))
        line_height = min(self.bounds.height, self._font_size * 1.35)
        y = self.bounds.y + max(0.0, (self.bounds.height - line_height) * 0.5)
        return Rect(self.bounds.x + self._padding, y, width, line_height)

    def _estimated_char_width(self) -> float:
        return max(1.0, self._font_size * 0.56)

    def _current_background(self) -> Color:
        if not self.enabled:
            return self._disabled_background
        if self._focused:
            return self._focused_background
        return self._background

    def _on_text_input(self, event: Event) -> None:
        if not self.enabled or self._read_only:
            return
        platform_event = self._platform_event(event, PlatformEventKind.TEXT_INPUT)
        if platform_event is None or platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        text = platform_event.text or ""
        text = self._normalize_inserted_text(text)
        if not text:
            return
        self._insert_text(text, reason="text_input")
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None or platform_event.key_code is None:
            return
        key = platform_event.key_code
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        handled = False
        if key in _LEFT_KEYS:
            self.caret_index = self._caret_index - 1
            handled = True
        elif key in _RIGHT_KEYS:
            self.caret_index = self._caret_index + 1
            handled = True
        elif key in _HOME_KEYS:
            self.caret_index = 0
            handled = True
        elif key in _END_KEYS:
            self.caret_index = len(self._value)
            handled = True
        elif key in _BACKSPACE_KEYS and not self._read_only:
            if self._caret_index > 0:
                index = self._caret_index
                self._replace_value(
                    self._value[: index - 1] + self._value[index:],
                    caret=index - 1,
                    reason="backspace",
                )
            handled = True
        elif key in _DELETE_KEYS and not self._read_only:
            if self._caret_index < len(self._value):
                index = self._caret_index
                self._replace_value(
                    self._value[:index] + self._value[index + 1 :],
                    caret=index,
                    reason="delete",
                )
            handled = True
        elif key in _RETURN_KEYS:
            handled = self._handle_return(event)

        if handled:
            event.prevent_default()

    def _handle_return(self, event: Event) -> bool:
        self.emit("submit", value=self._value, input_event=event)
        return True

    def _insert_text(self, text: str, *, reason: str) -> None:
        if self._max_length is not None:
            available = self._max_length - len(self._value)
            if available <= 0:
                return
            text = text[:available]
        index = self._caret_index
        new_value = self._value[:index] + text + self._value[index:]
        self._replace_value(new_value, caret=index + len(text), reason=reason)

    def _replace_value(self, value: str, *, caret: int, reason: str) -> None:
        old_value = self._value
        old_caret = self._caret_index
        self._value = value
        self._caret_index = max(0, min(caret, len(value)))
        if value != old_value:
            self.invalidate(reason=reason)
            self.emit("value_changed", old_value=old_value, value=value, reason=reason)
        elif self._caret_index != old_caret:
            self.invalidate(reason="caret")

    def _normalize_external_value(self, value: str) -> str:
        return value.replace("\r", " ").replace("\n", " ")

    def _normalize_inserted_text(self, value: str) -> str:
        return "".join(
            character
            for character in value
            if character.isprintable() and character not in "\r\n"
        )

    def _on_focus_gained(self, _event: Event) -> None:
        if not self._focused:
            self._focused = True
            self.invalidate(reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        if self._focused:
            self._focused = False
            self.invalidate(reason="focus_lost")

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


class PasswordInput(Input):
    """Single-line Input that never exposes its value through the visual scene."""

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        mask_character: str = "•",
        reveal: bool = False,
        accessible_name: str | None = None,
        **kwargs: object,
    ) -> None:
        normalized_mask = str(mask_character)
        if len(normalized_mask) != 1 or not normalized_mask.isprintable():
            raise ValueError("mask_character must be exactly one printable character.")
        self._mask_character = normalized_mask
        self._reveal = bool(reveal)
        super().__init__(
            value,
            bounds=bounds,
            accessible_name=accessible_name or "Password",
            **kwargs,
        )

    @property
    def mask_character(self) -> str:
        return self._mask_character

    @property
    def reveal(self) -> bool:
        return self._reveal

    @reveal.setter
    def reveal(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._reveal:
            return
        self._reveal = normalized
        self.invalidate(reason="reveal")

    def _display_value(self) -> str:
        if self._reveal:
            return self._value
        return self._mask_character * len(self._value)


class TextArea(Input):
    """Multiline retained text editor with line-aware caret navigation/rendering."""

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        line_spacing: float = 1.25,
        accessible_name: str | None = None,
        **kwargs: object,
    ) -> None:
        self._line_spacing = self._validate_positive(line_spacing, "line_spacing")
        super().__init__(
            value,
            bounds=bounds,
            accessible_name=accessible_name or "Text area",
            **kwargs,
        )

    def _normalize_external_value(self, value: str) -> str:
        return value.replace("\r\n", "\n").replace("\r", "\n")

    def _normalize_inserted_text(self, value: str) -> str:
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        return "".join(character for character in normalized if character == "\n" or character.isprintable())

    def _handle_return(self, _event: Event) -> bool:
        if self._read_only:
            return True
        self._insert_text("\n", reason="newline")
        return True

    def _append_content_nodes(self, node: SceneNode) -> None:
        content = Rect(
            self.bounds.x + self._padding,
            self.bounds.y + self._padding,
            max(0.0, self.bounds.width - (2.0 * self._padding)),
            max(0.0, self.bounds.height - (2.0 * self._padding)),
        )
        if content.width <= 0.0 or content.height <= 0.0:
            return

        line_height = self._font_size * self._line_spacing
        visible_count = max(1, int(content.height / line_height))
        lines = self._display_value().split("\n")
        before = self._value[: self._caret_index]
        caret_line = before.count("\n")
        caret_column = len(before.rsplit("\n", 1)[-1])
        first_line = max(0, min(caret_line - visible_count + 1, max(0, len(lines) - visible_count)))
        visible_lines = lines[first_line : first_line + visible_count]

        has_content = any(visible_lines)
        if has_content:
            for offset, line in enumerate(visible_lines):
                if not line:
                    continue
                node.add(
                    SceneNode(
                        key=f"{self.key}:line:{first_line + offset}",
                        kind=SceneNodeKind.TEXT,
                        bounds=Rect(
                            content.x,
                            content.y + (offset * line_height),
                            content.width,
                            line_height,
                        ),
                        fill=self._foreground,
                        text=line,
                        font_size=self._font_size,
                        font_family=self._font_family,
                        hit_testable=False,
                    )
                )
        elif self._placeholder:
            node.add(
                SceneNode(
                    key=f"{self.key}:placeholder",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(content.x, content.y, content.width, line_height),
                    fill=self._placeholder_color,
                    text=self._placeholder,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        if self._focused and self.enabled and not self._read_only:
            caret_row = caret_line - first_line
            if 0 <= caret_row < visible_count:
                caret_x = min(
                    content.x + content.width - 1.5,
                    content.x + (caret_column * self._estimated_char_width()),
                )
                node.add(
                    SceneNode(
                        key=f"{self.key}:caret",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            caret_x,
                            content.y + (caret_row * line_height),
                            1.5,
                            min(line_height, content.height - (caret_row * line_height)),
                        ),
                        fill=self._caret_color,
                        hit_testable=False,
                        z_index=2,
                    )
                )

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if (
            platform_event is not None
            and platform_event.key_code is not None
            and not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
        ):
            key = platform_event.key_code
            if key in _HOME_KEYS:
                self.caret_index = self._line_start(self._caret_index)
                event.prevent_default()
                return
            if key in _END_KEYS:
                self.caret_index = self._line_end(self._caret_index)
                event.prevent_default()
                return
        super()._on_key_down(event)

    def _line_start(self, index: int) -> int:
        previous = self._value.rfind("\n", 0, index)
        return 0 if previous < 0 else previous + 1

    def _line_end(self, index: int) -> int:
        following = self._value.find("\n", index)
        return len(self._value) if following < 0 else following
