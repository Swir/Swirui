import sys
import time

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    BackdropBlur,
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.BackdropBlurSmoke.{id(backend):x}"
    return backend


def _scene(accent_x: float) -> Scene:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 760.0, 460.0))
    root.add(
        SceneNode(
            "background",
            SceneNodeKind.RECTANGLE,
            Rect(0.0, 0.0, 760.0, 460.0),
            fill=Color.from_hex("#071225"),
            z_index=0,
        ),
        SceneNode(
            "accent-behind-glass",
            SceneNodeKind.RECTANGLE,
            Rect(accent_x, 90.0, 250.0, 250.0),
            fill=Color.from_hex("#007DFF"),
            corner_radius=CornerRadius.uniform(54.0),
            z_index=1,
        ),
    )
    glass = BackdropBlur(
        radius=22.0,
        corner_radius=CornerRadius.uniform(30.0),
    ).to_scene_node("glass", Rect(155.0, 105.0, 450.0, 245.0), z_index=2)
    glass.add(
        SceneNode(
            "glass-tint",
            SceneNodeKind.RECTANGLE,
            Rect(155.0, 105.0, 450.0, 245.0),
            fill=Color(0.07, 0.13, 0.24, 0.38),
            corner_radius=CornerRadius.uniform(30.0),
        ),
        SceneNode(
            "glass-title",
            SceneNodeKind.TEXT,
            Rect(205.0, 185.0, 350.0, 58.0),
            text="SwirUI Backdrop Blur",
            fill=Color.from_hex("#FFFFFF"),
            font_size=30.0,
            z_index=1,
        ),
    )
    root.add(
        glass,
        SceneNode(
            "foreground",
            SceneNodeKind.RECTANGLE,
            Rect(610.0, 330.0, 78.0, 78.0),
            fill=Color.from_hex("#21D4FD"),
            corner_radius=CornerRadius.uniform(20.0),
            z_index=3,
        ),
    )
    return Scene(760.0, 460.0, root)


@pytest.mark.skipif(sys.platform != "win32", reason="Native backdrop blur smoke requires Windows")
def test_backdrop_blur_uses_persistent_wgpu_context_and_blur_targets() -> None:
    renderer = WgpuRenderer()
    app = App(
        "SwirUI Backdrop Blur Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI Backdrop Blur Smoke", width=760, height=460)
    window.set_scene(_scene(95.0))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 4
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 0
        assert renderer.last_backdrop_count == 1
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend

        native_handle = window.native_handle
        assert native_handle is not None
        handle = native_handle.value
        context = renderer._contexts[handle]
        assert context.backdrop_pipeline_ready is True
        assert context.blur_target_size == window.pixel_size
        first_blur_generation = context.blur_generation
        assert first_blur_generation is not None

        window.set_scene(_scene(265.0))
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1

        assert renderer.frames_rendered == 2
        assert renderer.last_backdrop_count == 1
        assert renderer._contexts[handle] is context
        assert context.backdrop_pipeline_ready is True
        assert context.blur_generation == first_blur_generation
    finally:
        app.stop()
