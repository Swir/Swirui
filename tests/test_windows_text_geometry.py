"""Native glyph metrics and actual wgpu pixels for proportional input text."""

import ctypes
import sys

import pytest

from swirui import App, Button, IconButton, Input, Label, Panel, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Rect, WgpuRenderer
from swirui.rendering.text_layout import NativeTextShaper

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native fonts and wgpu")


def test_win32_word_shortcuts_select_and_delete_the_shaped_glyphs(record_property):
    renderer = WgpuRenderer(background=Color(0, 0, 0))
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=340, height=160))
    field = Input("iii WWW", bounds=Rect(20, 20, 260, 60), font_size=24,
                  focused_background=Color(0, 0, 0), selection_color=Color(0, 0, 1),
                  caret_color=Color(1, 0, 0))
    mount(window, field)
    try:
        app.start()
        app.process_events()
        window.focus_component(field)
        user32 = app.platform_backend._user32
        hwnd = window.native_handle.value
        send = user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t
        state = (ctypes.c_ubyte * 256)()
        assert user32.GetKeyboardState(state)

        def ctrl_key(key, *, shift=False):
            held = type(state).from_buffer_copy(state)
            held[0x11] = 0x80
            held[0x10] = 0x80 if shift else 0
            try:
                assert user32.SetKeyboardState(held)
                send(hwnd, 0x0100, key, 1)
                if key == 0x08:
                    send(hwnd, 0x0102, 0x7F, 1)  # Translated Ctrl+Backspace WM_CHAR.
                send(hwnd, 0x0101, key, 0xC0000001)
            finally:
                assert user32.SetKeyboardState(state)
            app.process_events()

        ctrl_key(0x25, shift=True)
        assert field.selected_text == "WWW" and field.caret_index == 4
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, _, rgba = renderer._contexts[hwnd].read_scene_rgba()
        layout = window._text_shaper.shape_line(field.value, 24, "Segoe UI", window.scale)
        y = round(59 * window.scale)
        blue = [x for x in range(width) if rgba[(width * y + x) * 4 + 2] > 180
                and rgba[(width * y + x) * 4] < 30]
        assert blue
        assert min(blue) == pytest.approx((30 + layout.carets[4]) * window.scale,
                                          abs=3 * window.scale)
        assert max(blue) == pytest.approx((30 + layout.carets[7]) * window.scale,
                                          abs=3 * window.scale)
        field.select(7, 7)
        ctrl_key(0x08)
        assert field.value == "iii " and field.caret_index == 4 and not field.selected_text
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        _, _, after = renderer._contexts[hwnd].read_scene_rgba()
        caret = [x for x in range(width) if after[(width * y + x) * 4] > 180
                 and after[(width * y + x) * 4 + 1] < 30]
        assert caret and min(caret) == pytest.approx(min(blue), abs=3 * window.scale)
        for row in range(round(31 * window.scale), round(60 * window.scale)):
            for x in range(max(caret) + 2, max(blue)):
                offset = (row * width + x) * 4
                assert max(after[offset:offset + 3]) < 10
        field.select(0, 0)
        ctrl_key(0x2E)
        assert field.value == "" and field.caret_index == 0
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
    finally:
        app.stop()


def test_action_labels_and_icons_center_their_ink_on_wgpu(record_property):
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=320, height=240))
    root = Panel(bounds=Rect(0, 0, 320, 240), background=Color(0, 0, 0))
    ink = Color(1, 1, 1)
    controls = (
        Button("iiiiWW", bounds=Rect(20, 20, 250, 40), foreground=ink, text_align="center"),
        Button("שלום", bounds=Rect(20, 80, 250, 40), foreground=ink, text_align="center"),
        IconButton("★", bounds=Rect(210, 145, 60, 60), accessible_name="Favorite", foreground=ink),
    )
    root.add(*controls)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        width, _, frame = renderer._contexts[window.native_handle.value].read_scene_rgba()
        for control in controls:
            box, scale = control.bounds, window.scale
            xs = [x for y in range(round(box.y * scale), round(box.bottom * scale))
                  for x in range(round(box.x * scale), round(box.right * scale))
                  if min(frame[(y * width + x) * 4:(y * width + x) * 4 + 3]) > 230]
            assert xs and (min(xs) + max(xs)) / 2 == pytest.approx(
                (box.x + box.width / 2) * scale, abs=3 * scale)
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
    finally:
        app.stop()


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


def test_fitted_title_keeps_all_native_glyphs_when_its_width_changes():
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=550, height=200))
    root = Panel(bounds=Rect(0, 0, 550, 200), background=Color(0, 0, 0))
    name = "Pracownia Światła Północy"
    title = Label(name, bounds=Rect(16, 16, 420, 48), color=Color(1, 1, 1),
                  font_size=31, min_font_size=16, clip_to_bounds=True)
    reference = Label(name, bounds=Rect(16, 96, 480, 48), color=Color(1, 1, 1))
    root.add(title, reference)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        widths = {size: window._text_shaper.shape_line(name, size, title.font_family,
                                                       window.scale).width
                  for size in range(16, 32)}

        def rows(frame, y):
            width, _, rgba = frame
            top = round(y * window.scale)
            bottom = top + round(48 * window.scale)
            return bytes(rgba[top * width * 4:bottom * width * 4])

        for available in (420, 245, 420):
            expected = max(size for size, width in widths.items() if width <= available)
            assert (expected < 31) == (available == 245)
            title.bounds = Rect(16, 16, available, 48)
            reference.font_size = expected
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            frame = context.read_scene_rgba()
            fitted = rows(frame, 16)
            assert max(fitted[::4]) == 255
            assert fitted == rows(frame, 96)
            assert title.build_scene_node().font_size == expected
            assert title.text == title.accessible_name == name and title.font_size == 31
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()


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
        layout = window._text_shaper.shape_line("iiiiWW", 24, "Segoe UI", window.scale)
        user32 = app.platform_backend._user32
        send = user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t
        hwnd = window.native_handle.value

        def mouse(message, flags, caret):
            x = round((30 + layout.carets[caret]) * window.scale)
            y = round(44 * window.scale)
            send(hwnd, message, flags, (y << 16) | x)
            app.process_events()

        mouse(0x0201, 1, 0)  # Left button down at the first glyph
        assert user32.GetCapture() == hwnd
        mouse(0x0200, 1, 4)  # Drag across the four narrow letters
        assert field.selected_text == "iiii"
        mouse(0x0202, 0, 4)
        assert window.pointer_capture_component is None and not user32.GetCapture()
        width, _height, rgba = pixels()
        # Below glyph ink, the blue selection ends at the fourth narrow letter.
        y = round(59 * window.scale)
        blue = [x for x in range(width) if rgba[(y * width + x) * 4 + 2] > 180]
        assert blue
        assert max(blue) == pytest.approx((30 + layout.carets[4]) * window.scale, abs=2)
        # A Shift+click delivered by Win32 keeps the original end of the selection anchored.
        mouse(0x0201, 0x0005, 6)
        mouse(0x0202, 0x0004, 6)
        assert field.selected_text == "iiiiWW"
    finally:
        app.stop()
