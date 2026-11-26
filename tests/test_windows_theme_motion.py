import sys
import time
from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    THEME_PRESETS,
    AnimationController,
    App,
    Button,
    Input,
    Panel,
    ThemeController,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_theme_switch_after_idle_presents_an_intermediate_gpu_frame(monkeypatch):
    renderer = WgpuRenderer()
    app = App(renderer=renderer)
    window = app.add_window(Window(width=360, height=240))
    root = Panel(bounds=Rect(0, 0, 360, 240))
    field = Input("Field notes", bounds=Rect(24, 30, 250, 40))
    root.add(field)
    mount(window, root)
    driver = AnimationController(app, window)
    light = replace(FUTURE_LIGHT, motion_duration=.24)
    themes = ThemeController(window, mode="dark", dark=FUTURE_DARK, light=light, animations=driver)
    try:
        app.start()
        app.process_events()
        window.focus_component(field)
        field.select(6, 11)
        context = renderer._contexts[window.native_handle.value]

        def surface_pixel():
            width, _, rgba = context.read_scene_rgba()
            i = 4 * (round(120 * window.scale) * width + round(40 * window.scale))
            return tuple(rgba[i:i + 3])

        now = time.monotonic()
        monkeypatch.setattr(time, "monotonic", lambda: now)
        now += 1
        app.invalidate(window)
        app.render_pending()
        dark_pixel = surface_pixel()
        now += 4  # The window has presented no frames since the user stopped editing.
        themes.mode = "light"
        now += .12
        assert app.render_pending() == 1
        assert surface_pixel() == dark_pixel
        now += .14
        assert app.render_pending() == 1
        middle = surface_pixel()
        now += .04
        assert app.render_pending() == 1
        light_pixel = surface_pixel()
        # The palette interpolates in linear light. Readback is encoded in sRGB.
        for start, mid, end in zip(dark_pixel, middle, light_pixel, strict=True):
            assert start + 12 < mid < end - 12
        target = light.text_color("surface")
        expected_pixel = tuple(round(channel * 255) for channel in (target.r, target.g, target.b))
        assert light_pixel == pytest.approx(expected_pixel, abs=1)
        assert root.theme is light and not themes.transitioning
        assert field.selected_text == "notes" and window.focused_component is field
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        themes.close()
        driver.dispose()
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_presets_and_intermediate_frames_match_real_gpu_pixels(record_property):
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=480, height=260))
    root = Panel(bounds=Rect(0, 0, 480, 260))
    field = Input("Keep draft", bounds=Rect(20, 100, 300, 44))
    root.add(Button("Create", bounds=Rect(20, 20, 180, 44)), field)
    mount(window, root)
    driver = AnimationController(app, window)
    controller = ThemeController(window, mode="dark", animations=driver)
    window.focus_component(field)
    field.select(0, 4)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        frames = 0

        def read_sample():
            nonlocal frames
            theme = root.theme
            scheduler = app._frame_schedulers[window]
            # App emits frame_rendered after presentation, advancing the next
            # sample. Compare readback against the sample submitted before it.
            now = scheduler.stats.last_frame_time + scheduler.frame_interval * 2
            app.render_pending(now)
            width, height, rgba = context.read_scene_rgba()
            for x, y, role in ((450, 210, "surface"), (100, 23, "accent")):
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                color = theme.text_color(role)
                assert tuple(rgba[offset:offset + 4]) == pytest.approx(
                    tuple(round(v * 255) for v in (color.r, color.g, color.b, color.a)), abs=1)
            assert field.value == "Keep draft" and field.selected_text == "Keep"
            assert window.focused_component is field
            assert renderer._contexts[window.native_handle.value] is context
            frames += 1
            return width, height

        for theme in THEME_PRESETS.values():
            controller.set_themes(light=theme, dark=theme)
            if controller.transitioning:
                driver.tick(theme.motion_duration / 2)
                assert root.theme != theme
                read_sample()
            driver.tick(1)
            width, height = read_sample()
            assert root.theme is theme and driver.active_count == 0
        record_property("native_rgba_readback", f"{width}x{height}")
        record_property("preset_count", len(THEME_PRESETS))
        record_property("verified_frames", frames)
        record_property("clock", "Deterministic ticks + actual App render cadence; no FPS claim")
    finally:
        driver.dispose()
        app.stop()
