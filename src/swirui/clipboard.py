"""Plain-text clipboard contract and an explicit in-memory implementation."""

from __future__ import annotations

from typing import Protocol

MAX_CLIPBOARD_BYTES = 16 * 1024 * 1024


class ClipboardError(RuntimeError):
    """Clipboard is unavailable, busy, malformed, or exceeds the text budget."""


class TextClipboard(Protocol):
    """Unicode text with LF line endings; None means no text format is available."""

    def read_text(self) -> str | None: ...

    def write_text(self, text: str) -> None: ...


def normalize_clipboard_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\0" in normalized:
        raise ClipboardError("Clipboard text cannot contain NUL characters.")
    try:
        size = len(normalized.replace("\n", "\r\n").encode("utf-16-le")) + 2
    except UnicodeEncodeError as exc:
        raise ClipboardError("Clipboard text contains invalid Unicode.") from exc
    if size > MAX_CLIPBOARD_BYTES:
        raise ClipboardError("Clipboard text exceeds the 16 MiB budget.")
    return normalized


class MemoryClipboard:
    """Isolated clipboard for tests or application-owned text exchange.

    This does not access the operating system clipboard. Share an instance across
    windows when an application intentionally wants shared in-memory contents.
    """

    def __init__(self, text: str | None = None) -> None:
        self._text = None if text is None else normalize_clipboard_text(text)

    def read_text(self) -> str | None:
        return self._text

    def write_text(self, text: str) -> None:
        self._text = normalize_clipboard_text(text)
