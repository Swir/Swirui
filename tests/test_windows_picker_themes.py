import sys
from datetime import date, time

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Calendar,
    ColorPicker,
    DatePicker,
    Panel,
    TimePicker,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu readback required")
def test_picker_themes_and_srgb_swatches_in_persistent_native_context(record_property):
    calendar = Calendar(bounds=Rect(20, 20, 420, 330), selected_date=date(2026, 10, 16))
    day = DatePicker(bounds=Rect(20, 380, 420, 64), value=date(2026, 10, 16))
    clock = TimePicker(bounds=Rect(20, 470, 420, 64), value=time(10, 30))
    color = ColorPicker(bounds=Rect(480, 20, 420, 330), value=Color.from_hex("#336699"))
    root = Panel(bounds=Rect(0, 0, 940, 570), theme=FUTURE_DARK)
    root.add(calendar, day, clock, color)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=940, height=570))
    mount(window, root)
    try:
        app.start()
        context = renderer._contexts[window.native_handle.value]
        window.focus_component(calendar)
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            color.set_channel_value("alpha", 1)
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, height, rgba = context.read_scene_rgba()
            nodes = {n.key: n for n in window.scene.walk()}

            def pixel(x, y, width=width, rgba=rgba):
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                return tuple(rgba[offset:offset + 3])

            def rgb(role, theme=theme):
                c = theme.text_color(role)
                return tuple(round(v * 255) for v in (c.r, c.g, c.b))

            assert pixel(330, 26) == pytest.approx(rgb("raised"), abs=1)
            assert pixel(21, 100) == pytest.approx(rgb("focus"), abs=1)
            for control, suffix in (
                (calendar, ":selected"), (day, ":active"), (clock, ":active")
            ):
                selected = next(n for n in nodes.values()
                                if n.key.startswith(control.key + ":") and n.key.endswith(suffix))
                sample = pixel(selected.bounds.right - 10, selected.bounds.bottom - 8)
                assert sample == pytest.approx(
                    rgb("selection"), abs=1
                )
            preview = nodes[color.key + ":preview"].bounds
            assert pixel(preview.x + 20, preview.y + 20) == pytest.approx((51, 102, 153), abs=1)
            assert color.hex_value == "#336699FF"
            # Adjacent hue strips must not acquire dark seams from separate
            # rectangle antialiasing. At full HSV value, at least one channel is 255.
            track = color.track_bounds("hue")
            thumb = nodes[color.key + ":thumb:hue"].bounds
            for x in range(int(track.x) + 2, int(track.right) - 2):
                if thumb.x - 3 <= x <= thumb.right + 3:
                    continue
                assert max(pixel(x, track.y + 8)) >= 253
            assert window.focused_component is calendar
            assert renderer._contexts[window.native_handle.value] is context
            color.set_channel_value("alpha", 0.5)
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, height, blended = context.read_scene_rgba()
            nodes = {n.key: n for n in window.scene.walk()}
            tile = nodes[color.key + ":checker:preview:0:0"]
            swatch = nodes[color.key + ":preview"].fill
            offset = (round((tile.bounds.y + 3) * window.scale) * width
                      + round((tile.bounds.x + 3) * window.scale)) * 4
            expected = []
            for foreground, background in zip(
                (swatch.r, swatch.g, swatch.b), (tile.fill.r, tile.fill.g, tile.fill.b), strict=True
            ):
                linear = 0.5 * foreground + 0.5 * background
                srgb = (
                    12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
                )
                expected.append(round(srgb * 255))
            assert tuple(blended[offset:offset + 3]) == pytest.approx(expected, abs=1)
        record_property("native_rgba_readback", f"{width}x{height}")
        record_property("verified_opaque_srgb_hex", "#336699")
    finally:
        app.stop()
