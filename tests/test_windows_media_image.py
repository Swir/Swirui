from __future__ import annotations

import base64
import sys

import pytest

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
    assert rgba[0:4] == [255, 0, 0, 255]
