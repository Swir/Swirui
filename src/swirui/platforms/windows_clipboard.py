"""Bounded CF_UNICODETEXT exchange, with explicit Win32 memory ownership.

See https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setclipboarddata
and https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getclipboarddata.
"""

from __future__ import annotations

import ctypes
from typing import Any

from swirui.clipboard import MAX_CLIPBOARD_BYTES, ClipboardError, normalize_clipboard_text

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


class Win32TextClipboard:
    """A small adapter; the platform backend validates the owning HWND."""

    def __init__(self, user32: Any, kernel32: Any) -> None:
        self._user32, self._kernel32 = user32, kernel32
        arguments: Any
        result: Any
        for name, arguments, result in (
            ("OpenClipboard", [ctypes.c_void_p], ctypes.c_int),
            ("CloseClipboard", [], ctypes.c_int),
            ("EmptyClipboard", [], ctypes.c_int),
            ("IsClipboardFormatAvailable", [ctypes.c_uint], ctypes.c_int),
            ("GetClipboardData", [ctypes.c_uint], ctypes.c_void_p),
            ("SetClipboardData", [ctypes.c_uint, ctypes.c_void_p], ctypes.c_void_p),
        ):
            function = getattr(user32, name)
            function.argtypes, function.restype = arguments, result
        for name, arguments, result in (
            ("GlobalAlloc", [ctypes.c_uint, ctypes.c_size_t], ctypes.c_void_p),
            ("GlobalFree", [ctypes.c_void_p], ctypes.c_void_p),
            ("GlobalLock", [ctypes.c_void_p], ctypes.c_void_p),
            ("GlobalUnlock", [ctypes.c_void_p], ctypes.c_int),
            ("GlobalSize", [ctypes.c_void_p], ctypes.c_size_t),
        ):
            function = getattr(kernel32, name)
            function.argtypes, function.restype = arguments, result

    def _open(self, hwnd: int) -> None:
        if not self._user32.OpenClipboard(hwnd):
            raise ClipboardError("Windows clipboard is busy or unavailable.")

    def read_text(self, hwnd: int) -> str | None:
        self._open(hwnd)
        try:
            if not self._user32.IsClipboardFormatAvailable(_CF_UNICODETEXT):
                return None
            handle = self._user32.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                raise ClipboardError("Windows could not retrieve clipboard text.")
            size = int(self._kernel32.GlobalSize(handle))
            if size < 2 or size > MAX_CLIPBOARD_BYTES:
                raise ClipboardError("Clipboard text allocation is invalid or too large.")
            pointer = self._kernel32.GlobalLock(handle)
            if not pointer:
                raise ClipboardError("Windows could not lock clipboard text.")
            try:
                raw = ctypes.string_at(pointer, size)
            finally:
                self._kernel32.GlobalUnlock(handle)
            end = next((i for i in range(0, len(raw) - 1, 2) if raw[i : i + 2] == b"\0\0"), None)
            if end is None:
                raise ClipboardError("Clipboard text has no Unicode terminator.")
            try:
                text = raw[:end].decode("utf-16-le")
            except UnicodeDecodeError as exc:
                raise ClipboardError("Clipboard text contains invalid Unicode.") from exc
            return normalize_clipboard_text(text)
        finally:
            self._user32.CloseClipboard()

    def write_text(self, hwnd: int, text: str) -> None:
        text = normalize_clipboard_text(text)
        payload = text.replace("\n", "\r\n").encode("utf-16-le") + b"\0\0"
        handle = self._kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(payload))
        if not handle:
            raise ClipboardError("Windows could not allocate clipboard text.")
        transferred = False
        try:
            pointer = self._kernel32.GlobalLock(handle)
            if not pointer:
                raise ClipboardError("Windows could not lock clipboard allocation.")
            try:
                ctypes.memmove(pointer, payload, len(payload))
            finally:
                self._kernel32.GlobalUnlock(handle)
            self._open(hwnd)
            try:
                if not self._user32.EmptyClipboard():
                    raise ClipboardError("Windows could not replace clipboard contents.")
                if not self._user32.SetClipboardData(_CF_UNICODETEXT, handle):
                    raise ClipboardError("Windows could not publish clipboard text.")
                transferred = True  # Windows owns the allocation from this point.
            finally:
                self._user32.CloseClipboard()
        finally:
            if not transferred:
                self._kernel32.GlobalFree(handle)
