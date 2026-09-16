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


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 smoke test requires Windows")
def test_win32_backend_creates_real_native_window() -> None:
    backend = Win32PlatformBackend()
    backend.initialize()

    displays = backend.displays()
    assert displays
    assert any(display.primary for display in displays)
    for display in displays:
        assert display.width > 0
        assert display.height > 0
        assert display.scale > 0.0
        assert display.effective_work_width > 0
        assert display.effective_work_height > 0

    handle = backend.create_window(NativeWindowSpec("SwirUI CI Native Smoke", 640, 420))
    assert handle.value > 0
    assert backend.window_scale(handle) > 0.0

    backend.set_window_title(handle, "SwirUI CI Native Smoke Updated")
    backend.resize_window(handle, 700, 460)
    backend.poll_events()
    backend.destroy_window(handle)
    backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 DPI smoke test requires Windows")
def test_win32_backend_normalizes_real_dpi_change_message() -> None:
    backend = Win32PlatformBackend()
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
        assert len(dpi_events) == 1
        assert dpi_events[0].scale == pytest.approx(1.5)
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
        platform_backend=Win32PlatformBackend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI Renderer Smoke", width=640, height=420)
    window.set_scene(Scene(640, 420, root))
    app.add_window(window)

    app.start()

    assert window.native_handle is not None
    assert renderer.frames_rendered == 1
    assert window.native_handle.value in renderer.surfaces

    app.stop()
    assert not renderer.surfaces
