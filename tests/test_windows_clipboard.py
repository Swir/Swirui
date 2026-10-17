"""Opt-in desktop integration: replaces clipboard contents with known test text.

Set SWIRUI_TEST_CLIPBOARD=1 on a desktop intended for native qualification.
This never reads or logs previous clipboard contents.
"""

import os
import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import NullRenderer


@pytest.mark.skipif(
    sys.platform != "win32" or os.environ.get("SWIRUI_TEST_CLIPBOARD") != "1",
    reason="Set SWIRUI_TEST_CLIPBOARD=1 to replace the Windows clipboard with test text.",
)
def test_real_windows_clipboard_exchanges_unicode_between_windows() -> None:
    app = App(platform_backend=Win32PlatformBackend(), renderer=NullRenderer())
    first = app.add_window(Window(title="SwirUI clipboard writer"))
    second = app.add_window(Window(title="SwirUI clipboard reader"))
    try:
        app.start()
        for value in ("SwirUI — Zażółć 🌍\nSecond line", "", "Second owner"):
            first.set_clipboard_text(value)
            assert second.get_clipboard_text() == value
        second.set_clipboard_text("SwirUI clipboard qualification complete")
        assert first.get_clipboard_text() == "SwirUI clipboard qualification complete"
    finally:
        app.stop()
