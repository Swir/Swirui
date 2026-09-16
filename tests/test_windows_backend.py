import sys

import pytest

from swirui import App, Window
from swirui.platforms import NativeWindowSpec
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
