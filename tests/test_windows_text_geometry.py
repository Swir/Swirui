"""Native glyph metrics and actual wgpu pixels for proportional input text."""

import sys

import pytest

from swirui import App, Input, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Rect, WgpuRenderer
from swirui.rendering.text_layout import NativeTextShaper

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native fonts and wgpu")


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_shaped_carets_follow_real_rasterized_proportional_text(scale):
    import _swirui_native as native

    shaper = NativeTextShaper(native.TextShaper())
    for text in ("iiiiWW", "open asset", "AVATAR", "office"):
        layout = shaper.shape_line(text, 24, "Segoe UI", scale)
        width = round(layout.width * scale)
        height = round(30 * scale)
        rgba = bytes(
            native.rasterize_text_rgba(text, width, height, 24 * scale, 1, 1, 1, 1, "Segoe UI")
        )
        ink = [x for y in range(height) for x in range(width) if rgba[(y * width + x) * 4 + 3]]
        assert ink
        # Advance includes the final glyph's side bearing, not a fixed-width
        # cell. Independent rasterization must end beside the proposed caret.
        gap = layout.carets[-1] * scale - max(ink)
        assert -1 <= gap <= 5 * scale, (text, scale, gap)
    narrow = shaper.shape_line("iiii", 24, "Segoe UI", scale)
    wide = shaper.shape_line("WWWW", 24, "Segoe UI", scale)
    assert wide.carets[-1] > 2 * narrow.carets[-1]


def test_native_unicode_positions_use_python_indices_and_real_rtl_geometry():
    import _swirui_native as native

    shaper = NativeTextShaper(native.TextShaper())
    for text in ("Aé😀e\u0301", "שלום", "abc אבג def"):
        layout = shaper.shape_line(text, 24, "Segoe UI", 1)
        assert len(layout.carets) == len(text) + 1
        assert all(0 <= x <= layout.width for x in layout.carets)
        assert layout.selection_spans(0, len(text))
    rtl = shaper.shape_line("שלום", 24, "Segoe UI", 1)
    assert rtl.carets[0] > rtl.carets[-1]


def test_real_wgpu_input_caret_sits_beside_text_and_selection_uses_font_width():
    field = Input(
        "iiiiWW",
        bounds=Rect(20, 20, 260, 60),
        font_size=24,
        background=Color(0, 0, 0),
        focused_background=Color(0, 0, 0),
        foreground=Color(1, 1, 1),
        caret_color=Color(1, 0, 0),
        selection_color=Color(0, 0, 1),
    )
    renderer = WgpuRenderer(background=Color(0, 0, 0))
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=400, height=240))
    mount(window, field)
    try:
        app.start()
        assert window._text_shaper is renderer._text_shaper is not None
        window.focus_component(field)
        context = renderer._contexts[window.native_handle.value]

        def pixels():
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            return context.read_scene_rgba()

        width, height, rgba = pixels()
        white, red = [], []
        for y in range(height):
            for x in range(width):
                r, g, b = rgba[(y * width + x) * 4 : (y * width + x) * 4 + 3]
                if min(r, g, b) > 180:
                    white.append(x)
                if r > 180 and max(g, b) < 30:
                    red.append(x)
        assert white and red
        assert -1 <= min(red) - max(white) <= 4 * window.scale
        field.select(0, 4)
        width, _height, rgba = pixels()
        # Below glyph ink, the blue selection ends at the fourth narrow letter.
        y = round(59 * window.scale)
        blue = [x for x in range(width) if rgba[(y * width + x) * 4 + 2] > 180]
        layout = window._text_shaper.shape_line("iiiiWW", 24, "Segoe UI", window.scale)
        assert blue
        assert max(blue) == pytest.approx((30 + layout.carets[4]) * window.scale, abs=2)
    finally:
        app.stop()
