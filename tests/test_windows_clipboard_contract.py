"""Win32 ownership/error contracts without modifying the desktop clipboard."""

import ctypes
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from swirui import ClipboardError
from swirui.platforms.windows_clipboard import Win32TextClipboard


def adapter(payload: bytes = b"h\0i\0\0\0"):
    buffer = ctypes.create_string_buffer(1024)
    ctypes.memmove(ctypes.addressof(buffer), payload, len(payload))
    user = SimpleNamespace(
        **{
            name: Mock(return_value=1)
            for name in (
                "OpenClipboard",
                "CloseClipboard",
                "EmptyClipboard",
                "IsClipboardFormatAvailable",
                "GetClipboardData",
                "SetClipboardData",
            )
        }
    )
    kernel = SimpleNamespace(
        GlobalAlloc=Mock(return_value=1),
        GlobalFree=Mock(return_value=0),
        GlobalLock=Mock(return_value=ctypes.addressof(buffer)),
        GlobalUnlock=Mock(return_value=0),
        GlobalSize=Mock(return_value=len(payload)),
    )
    return Win32TextClipboard(user, kernel), user, kernel, buffer


def test_write_transfers_movable_utf16_allocation_to_windows() -> None:
    clipboard, user, kernel, buffer = adapter()
    clipboard.write_text(123, "Zażółć 🌍\nline")
    expected = "Zażółć 🌍\r\nline".encode("utf-16-le") + b"\0\0"
    assert buffer.raw[: len(expected)] == expected
    kernel.GlobalAlloc.assert_called_once_with(2, len(expected))
    user.OpenClipboard.assert_called_once_with(123)
    user.SetClipboardData.assert_called_once_with(13, 1)
    kernel.GlobalFree.assert_not_called()
    kernel.GlobalUnlock.assert_called_once()
    user.CloseClipboard.assert_called_once()


@pytest.mark.parametrize(
    "failed", ["GlobalLock", "OpenClipboard", "EmptyClipboard", "SetClipboardData"]
)
def test_failed_write_releases_only_application_owned_allocation(failed: str) -> None:
    clipboard, user, kernel, _buffer = adapter()
    getattr(kernel if failed == "GlobalLock" else user, failed).return_value = 0
    with pytest.raises(ClipboardError):
        clipboard.write_text(123, "text")
    kernel.GlobalFree.assert_called_once_with(1)
    assert user.CloseClipboard.call_count == int(failed in ("EmptyClipboard", "SetClipboardData"))
    if failed in ("GlobalLock", "OpenClipboard"):
        user.EmptyClipboard.assert_not_called()


def test_read_copies_only_terminated_unicode_without_freeing_windows_memory() -> None:
    clipboard, user, kernel, _buffer = adapter("one\r\n🌍\0trailing".encode("utf-16-le"))
    assert clipboard.read_text(123) == "one\n🌍"
    kernel.GlobalUnlock.assert_called_once_with(1)
    kernel.GlobalFree.assert_not_called()
    user.CloseClipboard.assert_called_once()


@pytest.mark.parametrize("payload", [b"a\0b\0", b"\x00\xd8\0\0", b"x"])
def test_malformed_clipboard_is_rejected_and_closed(payload: bytes) -> None:
    clipboard, user, kernel, _buffer = adapter(payload)
    with pytest.raises(ClipboardError):
        clipboard.read_text(123)
    user.CloseClipboard.assert_called_once()
    kernel.GlobalFree.assert_not_called()


def test_oversize_read_is_rejected_before_memory_access() -> None:
    clipboard, user, kernel, _buffer = adapter()
    kernel.GlobalSize.return_value = 17 * 1024 * 1024
    with pytest.raises(ClipboardError):
        clipboard.read_text(123)
    kernel.GlobalLock.assert_not_called()
    user.CloseClipboard.assert_called_once()


def test_no_text_format_returns_none_and_does_not_request_data() -> None:
    clipboard, user, _kernel, _buffer = adapter()
    user.IsClipboardFormatAvailable.return_value = 0
    assert clipboard.read_text(123) is None
    user.GetClipboardData.assert_not_called()
    user.CloseClipboard.assert_called_once()
