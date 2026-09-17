import sys
import time

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    ColorFilter,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.ColorFilterSmoke.{id(backend):x}"
    return backend


def _scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
    )
    root.add(
        SceneNode(
            key="blue",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(70.0, 70.0, 210.0, 150.0),
            fill=Color(0.03, 0.48, 1.0, 1.0),
        ),
        SceneNode(
            key="orange",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(350.0, 120.0, 190.0, 130.0),
            fill=Color(1.0, 0.36, 0.05, 0.9),
        ),
        SceneNode(
            key="label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(120.0, 270.0, 400.0, 54.0),
            text="SwirUI GPU Color Matrix",
            fill=Color(1.0, 1.0, 1.0, 1.0),
            font_size=26.0,
        ),
    )
    return Scene(640.0, 360.0, root)


@pytest.mark.skipif(sys.platform != "win32", reason="Native color-filter smoke requires Windows")
def test_color_filter_reuses_real_persistent_wgpu_pipeline() -> None:
    initial_filter = ColorFilter.grayscale(0.7).then(ColorFilter.contrast(1.15))
    renderer = WgpuRenderer(color_filter=initial_filter, scene_blur_radius=3.0)
    app = App(
        "SwirUI Color Filter Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Color Filter Smoke", width=640, height=360)
    window.set_scene(_scene())
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        native_handle = window.native_handle
        assert native_handle is not None
        context = renderer._contexts[native_handle.value]
        assert context.color_filter_enabled is True
        assert context.color_filter_target_size == window.pixel_size
        assert context.color_filter_generation == 1
        assert context.blur_target_size == window.pixel_size
        first_context = context
        first_generation = context.color_filter_generation

        updated_filter = ColorFilter.hue_rotate(110.0).then(ColorFilter.saturation(1.3))
        renderer.set_color_filter(updated_filter)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1

        assert renderer.frames_rendered == 2
        assert renderer._contexts[native_handle.value] is first_context
        assert context.color_filter_enabled is True
        assert context.color_filter_generation == first_generation

        renderer.set_color_filter(None)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert context.color_filter_enabled is False
        assert context.color_filter_generation == first_generation
    finally:
        app.stop()
