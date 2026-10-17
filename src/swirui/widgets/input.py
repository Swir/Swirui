"""Retained editable text widgets with routed keyboard and text input."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from swirui.clipboard import ClipboardError
from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind
from swirui.rendering.text_layout import TextLineLayout, estimated_line
from swirui.theme import Theme

from .base import Widget
from .measurement import measure_text_block

if TYPE_CHECKING:
    from swirui.window import Window

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
_VK_C = 0x43
_VK_V = 0x56
_VK_X = 0x58

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
        theme: Theme | None = None,
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
        corner_radius: float | None = None,
        font_size: float = 16.0,
        font_family: str | None = None,
        padding: float = 10.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
        multiline: bool = False,
        mask_character: str | None = None,
        accessibility_role: AccessibilityRole = AccessibilityRole.TEXT_BOX,
    ) -> None:
        overrides = {
            "_background": background,
            "_focused_background": focused_background,
            "_disabled_background": disabled_background,
            "_foreground": foreground,
            "_placeholder_color": placeholder_color,
            "_selection_color": selection_color,
            "_caret_color": caret_color,
            "_corner_radius": corner_radius,
            "_font_family": font_family,
        }
        if theme is not None:
            background = background or theme.surface_color("raised")
            focused_background = focused_background or theme.surface_color("hover")
            disabled_background = disabled_background or theme.surface_color("disabled")
            foreground = foreground or theme.text_color("text")
            placeholder_color = placeholder_color or theme.text_color("muted")
            selection_color = selection_color or theme.surface_color("selection")
            caret_color = caret_color or theme.surface_color("focus")
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
        radius = (
            corner_radius if corner_radius is not None else (theme.control_radius if theme else 7.0)
        )
        self._corner_radius = self._validate_non_negative(radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(
            font_family if font_family is not None else (theme.font_family if theme else "Segoe UI")
        )
        self._padding = self._validate_non_negative(padding, "padding")
        self._caret = len(self._value)
        self._selection_anchor: int | None = None
        self._focused = False
        self._horizontal_offset = 0.0
        self._preferred_caret_x: float | None = None
        self._document_cache_value: str | None = None
        self._document_lines: list[str] = []
        self._document_starts: list[int] = []
        self._multiline_layouts: OrderedDict[tuple[object, ...], TextLineLayout] = OrderedDict()
        self._multiline_layout_chars = 0
        self._line_layout_key: tuple[object, ...] | None = None
        self._line_layout: TextLineLayout | None = None
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
        if font_family is not None:
            overrides["_font_family"] = self._font_family
        self._bind_theme(
            theme,
            {
                "_background": ("surface", "raised", _DEFAULT_BACKGROUND),
                "_focused_background": ("surface", "hover", _DEFAULT_FOCUSED_BACKGROUND),
                "_disabled_background": ("surface", "disabled", _DEFAULT_DISABLED_BACKGROUND),
                "_foreground": ("text", "text", _DEFAULT_FOREGROUND),
                "_placeholder_color": ("text", "muted", _DEFAULT_PLACEHOLDER),
                "_selection_color": ("surface", "selection", _DEFAULT_SELECTION),
                "_caret_color": ("surface", "focus", _DEFAULT_CARET),
                "_font_family": ("token", "font_family", "Segoe UI"),
                "_corner_radius": ("token", "control_radius", 7.0),
            },
            overrides,
        )

    def on_unmount(self, window: Window) -> None:
        super().on_unmount(window)
        # Layout keys include their provider; release the font system when a
        # detached control outlives its window instead of retaining it in LRU keys.
        self._line_layout_key = None
        self._line_layout = None
        self._multiline_layouts.clear()
        self._multiline_layout_chars = 0
        self._document_cache_value = None
        self._document_lines.clear()
        self._document_starts.clear()
        self._preferred_caret_x = None

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self._preferred_caret_x = None
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

    def intrinsic_size(self, available: Size | None = None) -> Size:
        """Measure rendered value/placeholder while preserving authored geometry."""

        rendered = self._display_value() if self._value else self._placeholder
        content_limit: float | None = None
        if self._multiline and available is not None:
            content_limit = max(0.0, available.width - (2.0 * self._padding))
        measured = measure_text_block(
            rendered,
            font_size=self._font_size,
            available_width=content_limit,
            line_height_factor=1.3,
            wrap=self._multiline,
        )
        natural = Size(
            measured.width + (2.0 * self._padding),
            measured.height + (2.0 * self._padding),
        )
        return Size(
            max(self.preferred_size.width, natural.width),
            max(self.preferred_size.height, natural.height),
        )

    def select(self, start: int, end: int) -> None:
        self._preferred_caret_x = None
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
        if (
            self._theme
            and self._focused
            and self.enabled
            and min(self.bounds.width, self.bounds.height) > 4
        ):
            root.fill = self._theme.surface_color("focus")
            root.add(
                SceneNode(
                    key=f"{self.key}:focus-surface",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(
                        self.bounds.x + 2,
                        self.bounds.y + 2,
                        self.bounds.width - 4,
                        self.bounds.height - 4,
                    ),
                    fill=self._current_background(),
                    corner_radius=CornerRadius.uniform(max(0, self._corner_radius - 2)),
                    hit_testable=False,
                    z_index=-1,
                )
            )
        if content.width <= 0.0 or content.height <= 0.0:
            return root

        if self._multiline:
            self._build_multiline_content(root, content)
        else:
            self._build_single_line_content(root, content)
        return root

    def _single_line_layout(self, text: str) -> TextLineLayout:
        window = self.mounted_window
        shaper = window._text_shaper if window is not None else None
        scale = window.scale if window is not None else 1.0
        key = (text, self._font_size, self._font_family, scale, shaper)
        if key != self._line_layout_key or self._line_layout is None:
            self._line_layout = (
                shaper.shape_line(text, self._font_size, self._font_family, scale)
                if shaper is not None
                else estimated_line(text, self._font_size)
            )
            self._line_layout_key = key
        return self._line_layout

    def _line_view_offset(self, layout: TextLineLayout, content: Rect) -> float:
        available = max(0.0, content.width - 1.5)
        caret = layout.carets[min(self._caret, len(layout.carets) - 1)]
        offset = min(self._horizontal_offset, max(0.0, layout.width - available))
        if caret < offset:
            offset = caret
        elif caret > offset + available:
            offset = caret - available
        self._horizontal_offset = max(0.0, offset)
        return self._horizontal_offset

    def _build_single_line_content(self, root: SceneNode, content: Rect) -> None:
        showing_placeholder = not self._value and bool(self._placeholder)
        text = self._placeholder if showing_placeholder else self._display_value()
        if showing_placeholder:
            text = " ".join(text.splitlines())
        layout = self._single_line_layout(text)
        offset = 0.0 if showing_placeholder else self._line_view_offset(layout, content)
        line_height = min(content.height, self._line_height())
        # Keep the complete shaped line intact. Cropping a string changes its
        # kerning/ligatures; a retained clip and pixel scroll preserve geometry.
        viewport = SceneNode(
            key=f"{self.key}:text-viewport",
            kind=SceneNodeKind.GROUP,
            bounds=content,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(viewport)
        if text:
            viewport.add(
                SceneNode(
                    key=f"{self.key}:text",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(content.x - offset, content.y, layout.width, line_height),
                    z_index=1,
                    fill=self._placeholder_color if showing_placeholder else self._foreground,
                    text=text,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        if not showing_placeholder:
            for index, (left, right) in enumerate(
                layout.selection_spans(self.selection_start, self.selection_end)
            ):
                x = max(content.x, content.x + left - offset)
                end = min(content.right, content.x + right - offset)
                if end > x:
                    viewport.add(
                        SceneNode(
                            key=f"{self.key}:selection" + (f":{index}" if index else ""),
                            kind=SceneNodeKind.RECTANGLE,
                            bounds=Rect(x, content.y, end - x, line_height),
                            z_index=0,
                            fill=self._selection_color,
                            hit_testable=False,
                        )
                    )
        if self._focused and self.enabled:
            caret = 0.0 if showing_placeholder else layout.carets[self._caret]
            viewport.add(
                SceneNode(
                    key=f"{self.key}:caret",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(content.x + caret - offset, content.y, 1.5, line_height),
                    z_index=2,
                    fill=self._caret_color,
                    hit_testable=False,
                )
            )

    def _multiline_layout(self, text: str) -> TextLineLayout:
        window = self.mounted_window
        shaper = window._text_shaper if window is not None else None
        scale = window.scale if window is not None else 1.0
        key = (text, self._font_size, self._font_family, scale, shaper)
        cached = self._multiline_layouts.get(key)
        if cached is not None:
            self._multiline_layouts.move_to_end(key)
            return cached
        layout = (
            shaper.shape_line(text, self._font_size, self._font_family, scale)
            if shaper is not None
            else estimated_line(text, self._font_size)
        )
        # Keep viewport work reusable without retaining an entire shaped document.
        if len(text) <= 65_536:
            self._multiline_layouts[key] = layout
            self._multiline_layout_chars += len(text)
            while len(self._multiline_layouts) > 128 or self._multiline_layout_chars > 65_536:
                old, _ = self._multiline_layouts.popitem(last=False)
                self._multiline_layout_chars -= len(str(old[0]))
        return layout

    def _lines(self) -> list[str]:
        if self._document_cache_value != self._value:
            self._document_lines = self._value.split("\n")
            self._document_starts = []
            offset = 0
            for line in self._document_lines:
                self._document_starts.append(offset)
                offset += len(line) + 1
            self._document_cache_value = self._value
        return self._document_lines

    def _multiline_horizontal_offset(self, content: Rect) -> float:
        starts = self._line_starts()
        index = self._line_index_for_position(self._caret, starts)
        layout = self._multiline_layout(self._lines()[index])
        caret_x = layout.carets[self._caret - starts[index]]
        available = max(0.0, content.width - 1.5)
        offset = min(self._horizontal_offset, max(0.0, layout.width - available))
        if caret_x < offset:
            offset = caret_x
        elif caret_x > offset + available:
            offset = caret_x - available
        self._horizontal_offset = max(0.0, offset)
        return self._horizontal_offset

    def _build_multiline_content(self, root: SceneNode, content: Rect) -> None:
        placeholder = not self._value and bool(self._placeholder)
        lines = (
            self._normalize_value(self._placeholder).split("\n") if placeholder else self._lines()
        )
        line_height = self._line_height()
        visible_lines = max(1, int(content.height / line_height))
        start = 0 if placeholder else self._multiline_view_start(visible_lines)
        offset = 0.0 if placeholder else self._multiline_horizontal_offset(content)
        starts = self._line_starts()
        caret_line = self._line_index_for_position(self._caret, starts)
        viewport = SceneNode(
            key=f"{self.key}:text-viewport",
            kind=SceneNodeKind.GROUP,
            bounds=content,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(viewport)
        for index in range(start, min(len(lines), start + visible_lines)):
            text = lines[index]
            layout = self._multiline_layout(text)
            y = content.y + (index - start) * line_height
            height = min(line_height, content.bottom - y)
            if text:
                viewport.add(
                    SceneNode(
                        key=f"{self.key}:text:{index}",
                        kind=SceneNodeKind.TEXT,
                        bounds=Rect(content.x - offset, y, layout.width, height),
                        text=text,
                        fill=self._placeholder_color if placeholder else self._foreground,
                        font_size=self._font_size,
                        font_family=self._font_family,
                        z_index=1,
                        hit_testable=False,
                    )
                )
            if placeholder:
                continue
            line_start = starts[index]
            left_index = max(0, self.selection_start - line_start)
            right_index = min(len(text), self.selection_end - line_start)
            spans = list(layout.selection_spans(left_index, right_index))
            line_end = line_start + len(text)
            if index < len(lines) - 1 and self.selection_start <= line_end < self.selection_end:
                newline_x = layout.carets[-1]
                spans.append((newline_x, newline_x + max(2.0, self._font_size * 0.25)))
            for part, (left, right) in enumerate(spans):
                x = max(content.x, content.x + left - offset)
                end_x = min(content.right, content.x + right - offset)
                if end_x > x:
                    viewport.add(
                        SceneNode(
                            key=f"{self.key}:selection:{index}:{part}",
                            kind=SceneNodeKind.RECTANGLE,
                            bounds=Rect(x, y, end_x - x, height),
                            fill=self._selection_color,
                            z_index=0,
                            hit_testable=False,
                        )
                    )
            if self._focused and self.enabled and index == caret_line:
                x = content.x + layout.carets[self._caret - line_start] - offset
                viewport.add(
                    SceneNode(
                        key=f"{self.key}:caret",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(x, y, 1.5, height),
                        fill=self._caret_color,
                        z_index=2,
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
            and key in (_VK_C, _VK_X, _VK_V)
        ):
            self._clipboard_action(key, event)
            event.prevent_default()
            return
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

    def _clipboard_action(self, key: int, event: Event) -> None:
        # Password fields accept paste but never expose their contents by copy/cut.
        if key in (_VK_C, _VK_X) and (self._mask_character is not None or not self.selected_text):
            return
        if self._read_only and key != _VK_C:
            return
        window = event.data.get("window") or self.mounted_window
        if window is None:
            return
        try:
            if key == _VK_V:
                text = window.get_clipboard_text()
                if text:
                    normalized = self._normalize_inserted_text(text, allow_tabs=True)
                    if normalized:
                        self._replace_selection(normalized, input_event=event)
            else:
                window.set_clipboard_text(self.selected_text)
                if key == _VK_X:
                    # Do not remove the selection unless the clipboard write succeeded.
                    self._replace_selection("", input_event=event)
        except ClipboardError as exc:
            self.emit(
                "clipboard_error",
                operation={_VK_C: "copy", _VK_X: "cut", _VK_V: "paste"}[key],
                error=exc,
                input_event=event,
            )

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
        self._preferred_caret_x = None
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
        starts = self._line_starts()
        lines = self._lines()
        current = self._line_index_for_position(self._caret, starts)
        preferred = self._preferred_caret_x
        if preferred is None:
            preferred = self._multiline_layout(lines[current]).carets[self._caret - starts[current]]
        target = max(0, min(current + delta, len(starts) - 1))
        column = self._multiline_layout(lines[target]).hit_test(preferred)
        self._move_caret(starts[target] + column, extend=extend)
        self._preferred_caret_x = preferred

    def _move_caret(self, index: int, *, extend: bool) -> None:
        self._preferred_caret_x = None
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
        self._lines()
        return self._document_starts

    @staticmethod
    def _line_index_for_position(position: int, line_starts: list[int]) -> int:
        return max(0, bisect_right(line_starts, position) - 1)

    def _line_end(self, line_start: int) -> int:
        newline = self._value.find("\n", line_start)
        return len(self._value) if newline < 0 else newline

    def _index_from_point(self, x: float, y: float) -> int:
        content = self._content_bounds()
        if not self._multiline:
            layout = self._single_line_layout(self._display_value())
            offset = self._line_view_offset(layout, content)
            return layout.hit_test(x - content.x + offset)

        line_starts = self._line_starts()
        visible_lines = max(1, int(content.height / self._line_height()))
        view_start = self._multiline_view_start(visible_lines)
        line = view_start + int(max(0.0, y - content.y) / self._line_height())
        line = max(0, min(line, len(line_starts) - 1))
        start = line_starts[line]
        layout = self._multiline_layout(self._lines()[line])
        offset = self._multiline_horizontal_offset(content)
        return start + layout.hit_test(x - content.x + offset)

    def _normalize_value(self, value: str) -> str:
        normalized = str(value).replace("\r\n", "\n").replace("\r", "\n")
        if self._multiline:
            return normalized.replace("\u2028", "\n").replace("\u2029", "\n")
        return normalized.replace("\n", "").replace("\u2028", "").replace("\u2029", "")

    def _normalize_inserted_text(self, text: str, *, allow_tabs: bool = False) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        filtered = "".join(
            char
            for char in normalized
            if char >= " " or (self._multiline and (char == "\n" or (allow_tabs and char == "\t")))
        )
        if self._multiline:
            return filtered.replace("\u2028", "\n").replace("\u2029", "\n")
        return filtered.replace("\n", "").replace("\u2028", "").replace("\u2029", "")

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
