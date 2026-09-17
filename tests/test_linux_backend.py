from __future__ import annotations

import os
import sys
import time

import pytest

from swirui.platforms import NativeWindowSpec, PlatformEventKind, PointerButton

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="The X11 backend is Linux-only.",
)


def test_linux_factory_selects_x11_when_display_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from swirui.platforms.factory import create_platform_backend

    monkeypatch.setenv("DISPLAY", os.environ.get("DISPLAY", ":99"))
    backend = create_platform_backend()

    assert backend.name == "x11"


def test_linux_factory_keeps_headless_backend_without_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from swirui.platforms.factory import create_platform_backend

    monkeypatch.delenv("DISPLAY", raising=False)
    backend = create_platform_backend()

    assert backend.name == "headless"


def test_x11_normalizes_tab_and_pointer_buttons() -> None:
    from swirui.platforms.linux import LinuxX11PlatformBackend

    assert LinuxX11PlatformBackend._normalize_key_code(0xFF09) == 0x09
    assert LinuxX11PlatformBackend._normalize_key_code(0xFE20) == 0x09
    assert LinuxX11PlatformBackend._normalize_key_code(ord("A")) == ord("A")
    assert LinuxX11PlatformBackend._pointer_button(1) is PointerButton.LEFT
    assert LinuxX11PlatformBackend._pointer_button(2) is PointerButton.MIDDLE
    assert LinuxX11PlatformBackend._pointer_button(3) is PointerButton.RIGHT
    assert LinuxX11PlatformBackend._pointer_button(4) is None


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="A real X11 display is required.")
def test_x11_creates_maps_resizes_and_destroys_real_window() -> None:
    from swirui.platforms.linux import LinuxX11PlatformBackend

    backend = LinuxX11PlatformBackend()
    backend.initialize()
    try:
        displays = backend.displays()
        assert len(displays) == 1
        assert displays[0].width > 0
        assert displays[0].height > 0
        assert displays[0].primary is True

        handle = backend.create_window(NativeWindowSpec("SwirUI X11 smoke", 640, 480))
        assert handle.value > 0
        assert backend.window_scale(handle) == 1.0
        assert backend.window_display(handle) == displays[0]

        backend.show_window(handle)
        backend.set_window_title(handle, "SwirUI X11 updated")
        backend.resize_window(handle, 700, 500)

        deadline = time.monotonic() + 2.0
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
