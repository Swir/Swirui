"""Read actual GPU pixels, including a reproducer on the legacy batch path."""

import sys
from collections.abc import Callable

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)
from swirui.rendering.affine_text_wgpu_renderer import WgpuRenderer as LegacyRenderer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows GPU required")


def test_gpu_pixels_preserve_path_rectangle_image_text_order(
    record_property: Callable[[str, object], None],
) -> None:
    def render(renderer: LegacyRenderer) -> tuple[int, bytes, float]:
        renderer.register_image_rgba("blue", 1, 1, bytes((0, 0, 255, 255)))
        bounds = Rect(0, 0, 200, 140)
        root = SceneNode("root", SceneNodeKind.GROUP, bounds)
        root.add(
            SceneNode(
                "red",
                SceneNodeKind.PATH,
                bounds,
                fill=Color(1, 0, 0),
                path=Path2D((Point(0, 0), Point(200, 0), Point(0, 140))),
            ),
            SceneNode("green", SceneNodeKind.RECTANGLE, Rect(20, 20, 40, 40), fill=Color(0, 1, 0)),
            SceneNode("blue-image", SceneNodeKind.IMAGE, Rect(30, 30, 20, 20), resource_id="blue"),
            SceneNode("yellow", SceneNodeKind.RECTANGLE, Rect(35, 35, 10, 10), fill=Color(1, 1, 0)),
            SceneNode(
                "text",
                SceneNodeKind.TEXT,
                Rect(70, 80, 110, 30),
                text="MMMM",
                font_size=24,
                fill=Color(1, 1, 1),
            ),
            SceneNode(
                "cyan-cover", SceneNodeKind.RECTANGLE, Rect(70, 80, 110, 30), fill=Color(0, 1, 1)
            ),
        )
        app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
        window = app.add_window(Window(width=200, height=140, min_width=100, min_height=100))
        window.set_scene(Scene(200, 140, root))
        try:
            app.start()
            assert window.native_handle is not None
            context = renderer._contexts[window.native_handle.value]
            assert hasattr(context, "draw_scene_ordered_cached")
            width, height, pixels = context.read_scene_rgba()
            assert len(pixels) == width * height * 4
            record_property("adapter", renderer.adapter_name)
            record_property("backend", renderer.graphics_backend)
            return width, bytes(pixels), window.scale
        finally:
            app.stop()

    def pixel(frame: tuple[int, bytes, float], x: int, y: int) -> tuple[int, ...]:
        width, pixels, scale = frame
        start = (round(y * scale) * width + round(x * scale)) * 4
        return tuple(pixels[start : start + 4])

    legacy = render(LegacyRenderer())
    assert pixel(legacy, 25, 25) == (255, 0, 0, 255)  # Reproduces the hidden green rectangle.
    assert pixel(legacy, 40, 40) == (0, 0, 255, 255)  # Image incorrectly covers later yellow.
    ordered = render(WgpuRenderer())
    assert pixel(ordered, 10, 10) == (255, 0, 0, 255)
    assert pixel(ordered, 25, 25) == (0, 255, 0, 255)
    assert pixel(ordered, 32, 32) == (0, 0, 255, 255)
    assert pixel(ordered, 40, 40) == (255, 255, 0, 255)
    assert all(
        pixel(ordered, x, y) == (0, 255, 255, 255)
        for x in range(72, 178, 3)
        for y in range(82, 108, 3)
    )
