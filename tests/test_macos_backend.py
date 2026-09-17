from __future__ import annotations

import sys
import time

import pytest

from swirui.platforms import NativeWindowSpec, PlatformEventKind, PointerButton

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="The Cocoa backend is macOS-only.",
)


def test_macos_factory_selects_cocoa_backend() -> None:
    from swirui.platforms.factory import create_platform_backend

    backend = create_platform_backend()

    assert backend.name == "cocoa"


def test_cocoa_normalizes_tab_key_code() -> None:
    from swirui.platforms.macos import MacOSCocoaPlatformBackend

    assert MacOSCocoaPlatformBackend._normalize_key_code(48) == 0x09
    assert MacOSCocoaPlatformBackend._normalize_key_code(0) == 0
    assert MacOSCocoaPlatformBackend._normalize_key_code(12) == 12


def test_cocoa_creates_shows_resizes_and_destroys_real_window() -> None:
    from swirui.platforms.macos import MacOSCocoaPlatformBackend

    backend = MacOSCocoaPlatformBackend()
    backend.initialize()
    try:
        displays = backend.displays()
        assert displays
        assert any(display.primary for display in displays)
        assert all(display.width > 0 and display.height > 0 for display in displays)
        assert all(display.scale > 0.0 for display in displays)
        assert all(display.refresh_rate_hz > 0.0 for display in displays)

        handle = backend.create_window(NativeWindowSpec("SwirUI Cocoa smoke", 640, 480))
        assert handle.value > 0
        assert backend.window_scale(handle) > 0.0
        assert backend.window_display(handle) is not None

        backend.show_window(handle)
        backend.set_window_title(handle, "SwirUI Cocoa updated")
        backend.resize_window(handle, 700, 500)

        deadline = time.monotonic() + 3.0
        events = []
        while time.monotonic() < deadline:
            events.extend(backend.poll_events())
            if any(
                event.kind is PlatformEventKind.RESIZE
                and event.width == 700
                and event.height == 500
                for event in events
            ):
                break
            time.sleep(0.01)

        assert any(
            event.kind is PlatformEventKind.RESIZE
            and event.width == 700
            and event.height == 500
            for event in events
        )

        backend.hide_window(handle)
        backend.destroy_window(handle)
        with pytest.raises(ValueError, match="Unknown native window handle"):
            backend.window_scale(handle)
    finally:
        backend.shutdown()


def test_cocoa_app_preserves_logical_geometry_on_scaled_display() -> None:
    from swirui import App, Window
    from swirui.platforms.macos import MacOSCocoaPlatformBackend

    backend = MacOSCocoaPlatformBackend()
    app = App(name="Cocoa geometry smoke", platform_backend=backend)
    window = Window(title="Retina logical geometry", width=640, height=480)
    app.add_window(window)
    app.start()
    try:
        assert window.native_handle is not None
        assert window.scale == pytest.approx(backend.window_scale(window.native_handle))
        assert window.width == 640
        assert window.height == 480
        assert window.pixel_width == round(640 * window.scale)
        assert window.pixel_height == round(480 * window.scale)

        backend.resize_window(
            window.native_handle,
            round(720 * window.scale),
            round(510 * window.scale),
        )
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and (window.width, window.height) != (720, 510):
            app.process_events()
            time.sleep(0.01)

        assert (window.width, window.height) == (720, 510)
        assert window.pixel_width == round(720 * window.scale)
        assert window.pixel_height == round(510 * window.scale)
    finally:
        app.stop()


def test_cocoa_pointer_button_mapping() -> None:
    from swirui.platforms.macos import (
        MacOSCocoaPlatformBackend,
        _NSEventTypeLeftMouseDown,
        _NSEventTypeLeftMouseUp,
        _NSEventTypeRightMouseDown,
        _NSEventTypeRightMouseUp,
    )

    backend = object.__new__(MacOSCocoaPlatformBackend)

    assert (
        backend._pointer_button(_NSEventTypeLeftMouseDown, 0)
        is PointerButton.LEFT
    )
    assert backend._pointer_button(_NSEventTypeLeftMouseUp, 0) is PointerButton.LEFT
    assert (
        backend._pointer_button(_NSEventTypeRightMouseDown, 0)
        is PointerButton.RIGHT
    )
    assert backend._pointer_button(_NSEventTypeRightMouseUp, 0) is PointerButton.RIGHT
