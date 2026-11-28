from __future__ import annotations

import base64
import sys

import pytest

from swirui import App, Component, Window, mount
from swirui.rendering import Point, Rect, WgpuRenderer
from swirui.widgets import Image, ImageFit

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native media gate is Windows-only")


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)
GIF_1X1 = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
SVG_RED = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2">'
    b'<rect width="2" height="2" fill="#ff0000"/></svg>'
)


def test_native_decodes_static_raster_gif_and_svg() -> None:
    import _swirui_native as native

    width, height, rgba = native.decode_image_rgba(PNG_1X1)
    assert (width, height) == (1, 1)
    assert len(rgba) == 4

    frames = native.decode_gif_rgba_frames(GIF_1X1)
    assert len(frames) == 1
    assert frames[0][0:2] == (1, 1)
    assert len(frames[0][3]) == 4

    width, height, rgba = native.decode_svg_rgba(SVG_RED, 4, 4)
    assert (width, height) == (4, 4)
    assert len(rgba) == 64
    assert rgba[0:4] == bytes((255, 0, 0, 255))


def test_cover_position_changes_visible_pixels_in_one_native_texture() -> None:
    renderer = WgpuRenderer()
    red, green, blue, yellow = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))
    top = bytes((*red, 255)) * 8 + bytes((*green, 255)) * 8
    bottom = bytes((*blue, 255)) * 8 + bytes((*yellow, 255)) * 8
    renderer.register_image_rgba("quadrants", 16, 16, top * 8 + bottom * 8)
    image = Image("quadrants", pixel_width=16, pixel_height=16, fit=ImageFit.COVER,
                  bounds=Rect(35, 30, 50, 100), image_position=Point(0, 0))
    app = App(renderer=renderer)
    window = app.add_window(Window(width=240, height=180))
    root = Component("root")
    root.add(image)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        uploads = renderer.image_native_uploads

        def check_color(x: int, y: int, expected: tuple[int, int, int]) -> None:
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, pixels = context.read_scene_rgba()

            def pixel(px: float, py: float) -> tuple[int, ...]:
                i = 4 * (round(py * window.scale) * width + round(px * window.scale))
                return tuple(pixels[i:i + 3])

            assert pixel(x, y) == expected
            assert pixel(image.bounds.x - 3, y) == pixel(1, 1)
            assert pixel(x, image.bounds.bottom + 3) == pixel(1, 1)

        check_color(60, 55, red)
        image.image_position = Point(1, 0)
        check_color(60, 55, green)
        image.bounds = Rect(35, 30, 100, 50)
        check_color(60, 55, red)
        image.image_position = Point(1, 1)
        check_color(60, 55, blue)
        assert renderer.image_gpu_resource_count == 1
        assert renderer.image_native_uploads == uploads == 1
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()
