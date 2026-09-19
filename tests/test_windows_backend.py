import ctypes
import sys
from typing import Any

import pytest

from swirui import App, Window
from swirui.platforms import NativeWindowSpec, PlatformEventKind
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    Win32PreviewRenderer,
)


class _SuggestedRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _isolated_backend(label: str) -> Win32PlatformBackend:
    """Create a backend with a process-unique Win32 class for smoke isolation.

    Win32 window classes remain registered for the lifetime of the process. The
    production runtime normally owns one platform backend, while this test module
    deliberately creates several independent backends in one pytest process.
    Giving each smoke backend its own class keeps its WNDPROC callback isolated.
    """

    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.NativeWindow.Tests.{label}.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 smoke test requires Windows")
def test_win32_backend_creates_real_native_window() -> None:
    backend = _isolated_backend("native")
    backend.initialize()

    displays = backend.displays()
    assert displays
    assert any(display.primary for display in displays)
    for display in displays:
        assert display.width > 0
        assert display.height > 0
        assert display.scale > 0.0
        assert display.refresh_rate_hz > 1.0
        assert display.effective_work_width > 0
        assert display.effective_work_height > 0

    handle = backend.create_window(NativeWindowSpec("SwirUI CI Native Smoke", 640, 420))
    assert handle.value > 0
    assert backend.window_scale(handle) > 0.0
    active_display = backend.window_display(handle)
    assert active_display is not None
    assert active_display.refresh_rate_hz > 1.0
    assert active_display.scale == pytest.approx(backend.window_scale(handle))

    backend.set_window_title(handle, "SwirUI CI Native Smoke Updated")
    backend.resize_window(handle, 700, 460)
    backend.poll_events()
    backend.destroy_window(handle)
    backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 DPI smoke test requires Windows")
def test_win32_backend_normalizes_real_dpi_change_message() -> None:
    backend = _isolated_backend("dpi")
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI DPI Smoke", 640, 420))

    try:
        win_dll: Any = ctypes.__dict__["WinDLL"]
        user32: Any = win_dll("user32", use_last_error=True)
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t

        suggested = _SuggestedRect(120, 80, 840, 540)
        dpi = 144
        packed_dpi = dpi | (dpi << 16)
        user32.SendMessageW(
            ctypes.c_void_p(handle.value),
            0x02E0,
            packed_dpi,
            ctypes.addressof(suggested),
        )

        events = backend.poll_events()
        dpi_events = [event for event in events if event.kind is PlatformEventKind.DPI_CHANGED]
        display_events = [
            event for event in events if event.kind is PlatformEventKind.DISPLAY_CHANGED
        ]
        assert len(dpi_events) == 1
        assert dpi_events[0].scale == pytest.approx(1.5)
        assert display_events
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 display smoke test requires Windows")
def test_win32_backend_normalizes_display_configuration_change() -> None:
    backend = _isolated_backend("display")
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI Display Smoke", 640, 420))

    try:
        win_dll: Any = ctypes.__dict__["WinDLL"]
        user32: Any = win_dll("user32", use_last_error=True)
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        user32.SendMessageW(ctypes.c_void_p(handle.value), 0x007E, 32, 0)

        events = backend.poll_events()
        display_events = [
            event for event in events if event.kind is PlatformEventKind.DISPLAY_CHANGED
        ]
        assert display_events
        assert all(event.window == handle for event in display_events)
        assert backend.window_display(handle) is not None
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 keyboard smoke test requires Windows")
def test_win32_backend_normalizes_real_keyboard_and_system_key_messages() -> None:
    backend = _isolated_backend("keyboard")
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI Keyboard Smoke", 640, 420))

    try:
        win_dll: Any = ctypes.__dict__["WinDLL"]
        user32: Any = win_dll("user32", use_last_error=True)
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        backend.poll_events()

        user32.SendMessageW(ctypes.c_void_p(handle.value), 0x0100, 0x09, 0)
        user32.SendMessageW(ctypes.c_void_p(handle.value), 0x0104, 0x79, 0)
        events = backend.poll_events()
        key_events = [event for event in events if event.kind is PlatformEventKind.KEY_DOWN]

        assert len(key_events) == 2
        tab_event, system_event = key_events
        assert tab_event.window == handle
        assert tab_event.key_code == 0x09
        assert tab_event.shift is False
        assert tab_event.ctrl is False
        assert tab_event.alt is False
        assert tab_event.meta is False
        assert system_event.window == handle
        assert system_event.key_code == 0x79
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Win32 pointer capture smoke test requires Windows",
)
def test_win32_backend_acquires_and_releases_real_pointer_capture() -> None:
    backend = _isolated_backend("pointer-capture")
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI Pointer Capture Smoke", 640, 420))

    try:
        assert backend.capture_pointer(handle) is True

        win_dll: Any = ctypes.__dict__["WinDLL"]
        user32: Any = win_dll("user32", use_last_error=True)
        user32.GetCapture.argtypes = []
        user32.GetCapture.restype = ctypes.c_void_p
        assert int(user32.GetCapture()) == handle.value

        assert backend.release_pointer(handle) is True
        assert not user32.GetCapture()
        assert backend.release_pointer(handle) is False
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 renderer smoke test requires Windows")
def test_win32_preview_renderer_paints_scene_into_real_window() -> None:
    root = SceneNode(
        "background",
        SceneNodeKind.GROUP,
        Rect(0, 0, 640, 420),
        fill=Color.from_hex("#08101E"),
    )
    root.add(
        SceneNode(
            "card",
            SceneNodeKind.RECTANGLE,
            Rect(40, 40, 360, 180),
            fill=Color.from_hex("#0D5C87"),
            corner_radius=CornerRadius.uniform(24),
        ),
        SceneNode(
            "label",
            SceneNodeKind.TEXT,
            Rect(72, 82, 300, 48),
            text="SwirUI renderer smoke",
            fill=Color.from_hex("#FFFFFF"),
            font_size=26,
        ),
    )

    renderer = Win32PreviewRenderer()
    app = App(
        "SwirUI Renderer Smoke",
        platform_backend=_isolated_backend("preview"),
        renderer=renderer,
    )
    window = Window(title="SwirUI Renderer Smoke", width=640, height=420)
    window.set_scene(Scene(640, 420, root))
    app.add_window(window)

    app.start()

    assert window.native_handle is not None
    assert window.display is not None
    assert window.display.refresh_rate_hz > 1.0
    assert renderer.frames_rendered == 1
    assert window.native_handle.value in renderer.surfaces

    app.stop()
    assert not renderer.surfaces
