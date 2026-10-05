"""Bounded retained Markdown viewer with local-only sanitized rendering."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from swirui.core import AccessibilityRole, Event
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .measurement import measure_text_block
from .scroll_events import routed_scroll_deltas, update_scroll_residual

_VK_PAGE_UP = 0x21
_VK_PAGE_DOWN = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_UP = 0x26
_VK_DOWN = 0x28

_TAG_RE = re.compile(r"<[^>\n]+>")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^\n)]*\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\([^\n)]*\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_LIST_RE = re.compile(r"^\s*[-+*]\s+(.+)$")
_ORDERED_RE = re.compile(r"^\s*(\d{1,6})[.)]\s+(.+)$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_FENCE = chr(96) * 3
_TILDE_FENCE = "~" * 3

_BG = Color.from_hex("#0B1118")
_FG = Color.from_hex("#D8E1EA")
_HEADING = Color.from_hex("#7DD3FC")
_MUTED = Color.from_hex("#93A4B5")
_CODE_BG = Color.from_hex("#101923")
_CODE_FG = Color.from_hex("#C9D7E5")
_ACCENT = Color.from_hex("#38BDF8")


@dataclass(frozen=True, slots=True)
class _Block:
    kind: str
    text: str
    level: int = 0


@dataclass(frozen=True, slots=True)
class _Line:
    kind: str
    text: str
    y: float
    height: float
    size: float
    indent: float


class MarkdownViewer(Widget):
    """Render a safe local Markdown subset without executing or fetching content."""

    def __init__(
        self,
        markdown: str = "",
        *,
        bounds: Rect,
        key: str | None = None,
        font_size: float = 15.0,
        font_family: str = "Segoe UI",
        code_font_family: str = "Cascadia Mono",
        padding: float = 14.0,
        max_blocks: int = 4096,
        max_chars: int = 500_000,
        max_scene_nodes: int = 192,
        background: Color | None = None,
        foreground: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = "Markdown viewer",
        accessible_description: str | None = None,
    ) -> None:
        self._font_size = self._positive(font_size, "font_size")
        self._font_family = self._family(font_family, "font_family")
        self._code_font_family = self._family(code_font_family, "code_font_family")
        self._padding = self._non_negative(padding, "padding")
        self._max_blocks = self._limit(max_blocks, "max_blocks", 1)
        self._max_chars = self._limit(max_chars, "max_chars", 64)
        self._max_scene_nodes = self._limit(max_scene_nodes, "max_scene_nodes", 8)
        self._background = background or _BG
        self._foreground = foreground or _FG
        self._markdown = ""
        self._blocks: tuple[_Block, ...] = ()
        self._truncated = False
        self._scroll_y = 0.0
        self._layout_width: float | None = None
        self._lines: tuple[_Line, ...] = ()
        self._content_height = 0.0
        self._scalar_width_cache: dict[tuple[str, float], float] = {}
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name or "Markdown viewer",
            accessible_description=(
                accessible_description
                or "Sanitized local Markdown; remote media and raw markup are never executed."
            ),
        )
        self._set_markdown(markdown, invalidate=False)
        self._sync_accessibility()
        self.on("pointer_scroll", self._on_pointer_scroll)
        self.on("key_down", self._on_key_down)

    @property
    def markdown(self) -> str:
        return self._markdown

    @markdown.setter
    def markdown(self, value: str) -> None:
        self._set_markdown(value, invalidate=True)

    @property
    def block_count(self) -> int:
        return len(self._blocks)

    @property
    def truncated(self) -> bool:
        return self._truncated

    @property
    def scroll_y(self) -> float:
        return self._scroll_y

    @scroll_y.setter
    def scroll_y(self, value: float) -> None:
        self.scroll_to(value)

    @property
    def content_height(self) -> float:
        self._ensure_layout()
        return self._content_height + (2.0 * self._padding)

    @property
    def max_scroll_y(self) -> float:
        return max(0.0, self.content_height - self.bounds.height)

    @property
    def sanitized_text(self) -> str:
        """Return inert textual content retained after Markdown sanitization."""

        return "\n".join(block.text for block in self._blocks if block.text)

    def scroll_to(self, y: float) -> bool:
        target = min(max(0.0, self._finite(y, "scroll_y")), self.max_scroll_y)
        if math.isclose(target, self._scroll_y, abs_tol=1e-9):
            return False
        self._scroll_y = target
        self._sync_accessibility()
        self.invalidate(reason="markdown_scroll")
        self.emit("scrolled", offset=self._scroll_y, max_offset=self.max_scroll_y)
        return True

    def scroll_by(self, dy: float) -> bool:
        return self.scroll_to(self._scroll_y + self._finite(dy, "dy"))

    def build_scene_node(self) -> SceneNode:
        self._ensure_layout()
        self._scroll_y = min(max(0.0, self._scroll_y), self.max_scroll_y)
        self._sync_accessibility()
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        top = self.bounds.y + self._padding
        bottom = self.bounds.bottom - self._padding
        left = self.bounds.x + self._padding
        right = self.bounds.right - self._padding
        if bottom <= top or right <= left:
            return root

        emitted = 0
        for index, line in enumerate(self._lines):
            y = top + line.y - self._scroll_y
            if y + line.height <= top:
                continue
            required_nodes = 2 if line.kind in {"code", "quote"} else 1
            if y >= bottom or emitted + required_nodes > self._max_scene_nodes:
                break
            x = left + line.indent
            width = max(0.0, right - x)
            if line.kind == "code":
                root.add(
                    SceneNode(
                        key=f"{self.key}:code-bg:{index}",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(max(left, x - 4.0), y, width + 4.0, line.height),
                        fill=_CODE_BG,
                        hit_testable=False,
                    )
                )
                emitted += 1
            elif line.kind == "quote":
                root.add(
                    SceneNode(
                        key=f"{self.key}:quote:{index}",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(left, y, 2.0, line.height),
                        fill=_ACCENT,
                        hit_testable=False,
                    )
                )
                emitted += 1
            root.add(
                SceneNode(
                    key=f"{self.key}:text:{index}",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(x, y, width, line.height),
                    fill=self._color_for(line.kind),
                    text=line.text,
                    font_size=line.size,
                    font_family=(
                        self._code_font_family if line.kind == "code" else self._font_family
                    ),
                    hit_testable=False,
                )
            )
            emitted += 1
        return root

    def _set_markdown(self, value: str, *, invalidate: bool) -> None:
        source = str(value).replace("\r\n", "\n").replace("\r", "\n")
        source = _CONTROL_RE.sub("", source)
        source_truncated = len(source) > self._max_chars
        source = source[: self._max_chars]
        blocks, block_truncated = self._parse(source)
        self._markdown = source
        self._blocks = blocks
        self._truncated = source_truncated or block_truncated
        self._scroll_y = 0.0
        self._layout_width = None
        self._lines = ()
        self._content_height = 0.0
        if invalidate:
            self._sync_accessibility()
            self.invalidate(reason="markdown")

    def _parse(self, source: str) -> tuple[tuple[_Block, ...], bool]:
        blocks: list[_Block] = []
        paragraph: list[str] = []
        code: list[str] = []
        fence: str | None = None
        truncated = False

        def append(kind: str, text: str, level: int = 0) -> bool:
            nonlocal truncated
            if len(blocks) >= self._max_blocks:
                truncated = True
                return False
            blocks.append(_Block(kind, text, level))
            return True

        def flush() -> bool:
            if not paragraph:
                return True
            text = self._sanitize(" ".join(part.strip() for part in paragraph))
            paragraph.clear()
            return not text or append("paragraph", text)

        for raw in source.split("\n"):
            stripped = raw.strip()
            if fence is not None:
                if stripped.startswith(fence):
                    if not append("code", "\n".join(code)):
                        break
                    code.clear()
                    fence = None
                else:
                    code.append(raw.expandtabs(4))
                continue
            if stripped.startswith(_FENCE) or stripped.startswith(_TILDE_FENCE):
                if not flush():
                    break
                fence = stripped[:3]
                code.clear()
                continue
            if not stripped:
                if not flush():
                    break
                continue
            heading = _HEADING_RE.match(stripped)
            if heading is not None:
                if not flush() or not append(
                    "heading", self._sanitize(heading.group(2)), len(heading.group(1))
                ):
                    break
                continue
            item = _LIST_RE.match(raw)
            if item is not None:
                if not flush() or not append("list", "• " + self._sanitize(item.group(1))):
                    break
                continue
            ordered = _ORDERED_RE.match(raw)
            if ordered is not None:
                if not flush() or not append(
                    "list", f"{ordered.group(1)}. {self._sanitize(ordered.group(2))}"
                ):
                    break
                continue
            if stripped.startswith(">"):
                if not flush() or not append("quote", self._sanitize(stripped[1:].lstrip())):
                    break
                continue
            paragraph.append(raw)

        if fence is not None and code and not truncated:
            append("code", "\n".join(code))
        if paragraph and not truncated:
            flush()
        return tuple(blocks), truncated

    @staticmethod
    def _sanitize(text: str) -> str:
        value = _IMAGE_RE.sub(lambda match: f"[image: {match.group(1).strip()}]", text)
        value = _LINK_RE.sub(lambda match: match.group(1), value)
        value = _TAG_RE.sub("", value)
        value = value.replace(chr(96), "")
        for marker in ("***", "___", "**", "__", "~~"):
            value = value.replace(marker, "")
        return " ".join(value.split()).strip(" *_")

    def _ensure_layout(self) -> None:
        width = max(0.0, self.bounds.width - (2.0 * self._padding))
        if self._layout_width is not None and math.isclose(
            width, self._layout_width, abs_tol=1e-9
        ):
            return
        lines: list[_Line] = []
        y = 0.0
        for block in self._blocks:
            kind = block.kind
            size = self._font_size
            indent = 0.0
            if kind == "heading":
                size *= max(1.05, 1.6 - (0.1 * max(0, block.level - 1)))
            elif kind == "list":
                indent = 12.0
            elif kind == "quote":
                indent = 16.0
            elif kind == "code":
                indent = 8.0
                size *= 0.94
            source_lines = block.text.split("\n") if kind == "code" else [block.text]
            available = max(1.0, width - indent)
            for source_line in source_lines:
                wrapped = (
                    self._wrap_preserving_spaces(source_line, available, size)
                    if kind == "code"
                    else self._wrap(source_line, available, size)
                )
                for visible in wrapped:
                    height = (size * 1.34) + 4.0
                    lines.append(_Line(kind, visible, y, height, size, indent))
                    y += height
            y += 10.0
        self._layout_width = width
        self._lines = tuple(lines)
        self._content_height = max(0.0, y - 10.0 if y else 0.0)

    def _wrap(self, text: str, width: float, size: float) -> tuple[str, ...]:
        if not text:
            return ("",)
        result: list[str] = []
        current = ""
        for word in text.split():
            candidate = word if not current else f"{current} {word}"
            if self._text_width(candidate, size) <= width:
                current = candidate
                continue
            if current:
                result.append(current)
                current = ""
            if self._text_width(word, size) <= width:
                current = word
            else:
                pieces = self._split_token(word, width, size)
                result.extend(pieces[:-1])
                current = pieces[-1] if pieces else ""
        if current or not result:
            result.append(current)
        return tuple(result)

    def _split_token(self, token: str, width: float, size: float) -> tuple[str, ...]:
        return self._wrap_preserving_spaces(token, width, size)

    def _wrap_preserving_spaces(
        self, text: str, width: float, size: float
    ) -> tuple[str, ...]:
        """Wrap one logical line without collapsing code whitespace.

        Width is accumulated per scalar instead of repeatedly measuring an
        ever-growing prefix, keeping very long unbroken tokens linear in input
        size while preserving indentation and repeated spaces in code blocks.
        """

        if not text:
            return ("",)
        parts: list[str] = []
        current: list[str] = []
        current_width = 0.0
        for char in text:
            char_width = self._scalar_width(char, size)
            if current and current_width + char_width > width:
                parts.append("".join(current))
                current = [char]
                current_width = char_width
            else:
                current.append(char)
                current_width += char_width
        if current:
            parts.append("".join(current))
        return tuple(parts)

    def _scalar_width(self, char: str, size: float) -> float:
        key = (char, size)
        cached = self._scalar_width_cache.get(key)
        if cached is not None:
            return cached
        width = measure_text_block(char, font_size=size, wrap=False).width
        if len(self._scalar_width_cache) < 256:
            self._scalar_width_cache[key] = width
        return width

    @staticmethod
    def _text_width(text: str, size: float) -> float:
        return measure_text_block(text, font_size=size, wrap=False).width

    def _color_for(self, kind: str) -> Color:
        if kind == "heading":
            return _HEADING
        if kind == "code":
            return _CODE_FG
        if kind in {"quote", "list"}:
            return _MUTED
        return self._foreground

    def _sync_accessibility(self) -> None:
        maximum = self.max_scroll_y
        self.accessible_value = self._scroll_y
        self.accessible_min_value = 0.0
        self.accessible_max_value = maximum
        suffix = "; truncated" if self._truncated else ""
        self.accessible_value_text = (
            f"{len(self._blocks)} markdown blocks; "
            f"scroll {self._scroll_y:.0f} of {maximum:.0f} DIPs{suffix}"
        )

    def _on_pointer_scroll(self, event: Event) -> None:
        if not self.enabled or not self.visible:
            return
        deltas = routed_scroll_deltas(event)
        if deltas is None:
            return
        delta_x, delta_y = deltas
        before = self._scroll_y
        if delta_y:
            self._scroll_y = min(max(0.0, before + delta_y), self.max_scroll_y)
        consumed_y = self._scroll_y - before
        if not math.isclose(consumed_y, 0.0, abs_tol=1e-9):
            self._sync_accessibility()
            self.invalidate(reason="markdown_scroll")
        update_scroll_residual(
            event,
            delta_x=delta_x,
            delta_y=delta_y - consumed_y,
            consumed=not math.isclose(consumed_y, 0.0, abs_tol=1e-9),
        )

    def _on_key_down(self, event: Event) -> None:
        platform_event = event.data.get("event")
        if (
            event.default_prevented
            or not self.enabled
            or not isinstance(platform_event, PlatformEvent)
            or platform_event.kind is not PlatformEventKind.KEY_DOWN
            or platform_event.key_code is None
            or platform_event.ctrl
            or platform_event.alt
            or platform_event.meta
        ):
            return
        page = max(self._font_size * 2.0, self.bounds.height - (2.0 * self._padding))
        changed = False
        if platform_event.key_code == _VK_UP:
            changed = self.scroll_by(-self._font_size * 2.0)
        elif platform_event.key_code == _VK_DOWN:
            changed = self.scroll_by(self._font_size * 2.0)
        elif platform_event.key_code == _VK_PAGE_UP:
            changed = self.scroll_by(-page)
        elif platform_event.key_code == _VK_PAGE_DOWN:
            changed = self.scroll_by(page)
        elif platform_event.key_code == _VK_HOME:
            changed = self.scroll_to(0.0)
        elif platform_event.key_code == _VK_END:
            changed = self.scroll_to(self.max_scroll_y)
        if changed:
            event.prevent_default()

    @staticmethod
    def _finite(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite.")
        return normalized

    @classmethod
    def _positive(cls, value: float, name: str) -> float:
        normalized = cls._finite(value, name)
        if normalized <= 0.0:
            raise ValueError(f"{name} must be greater than zero.")
        return normalized

    @classmethod
    def _non_negative(cls, value: float, name: str) -> float:
        normalized = cls._finite(value, name)
        if normalized < 0.0:
            raise ValueError(f"{name} must be non-negative.")
        return normalized

    @staticmethod
    def _limit(value: int, name: str, minimum: int) -> int:
        normalized = int(value)
        if normalized < minimum:
            raise ValueError(f"{name} must be at least {minimum}.")
        return normalized

    @staticmethod
    def _family(value: str, name: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError(f"{name} cannot be empty.")
        return normalized
