import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    AnimationController,
    App,
    Button,
    Panel,
    SilkRibbon,
    SurfaceInteraction,
    SurfaceStyle,
    ThemeSurface,
    Window,
    mount,
)
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_satin_fold_is_continuous_across_dark_and_light_gpu_frames():
    renderer = WgpuRenderer()
    app = App(renderer=renderer)
    window = app.add_window(Window(width=640, height=320))
    root = Panel(bounds=Rect(0, 0, 640, 320), theme=FUTURE_DARK)
    ribbon = SilkRibbon(bounds=Rect(18.25, 22.5, 554.75, 240))
    root.add(ribbon)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        for theme, accent in ((FUTURE_DARK, "#28DEB0"), (FUTURE_LIGHT, "#E67434")):
            root.theme = theme.with_accent(accent)
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, pixels = context.read_scene_rgba()
            top = round(ribbon.bounds.y * window.scale)
            bottom = round(ribbon.bounds.bottom * window.scale)
            for fraction in (.23, .51, .74):
                x = round((ribbon.bounds.x + fraction * ribbon.bounds.width) * window.scale)
                column = [tuple(pixels[(y * width + x) * 4:(y * width + x) * 4 + 3])
                          for y in range(top, bottom)]
                background = column[0]
                assert column[-1] == background
                painted = [y for y, rgb in enumerate(column) if rgb != background]
                assert len(painted) > 20
                assert painted[-1] - painted[0] + 1 == len(painted)
                colors = {column[y] for y in painted}
                assert len(colors) >= 10
                if theme is FUTURE_DARK:
                    assert any(g - r > 60 for r, g, _ in colors)
                else:
                    assert any(r - g > 40 for r, g, _ in colors)
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_surface_feedback_presents_distinct_gpu_frames_in_both_themes(record_property):
    renderer = WgpuRenderer()
    app = App(renderer=renderer)
    window = app.add_window(Window(width=640, height=400))
    root = Panel(bounds=Rect(0, 0, 640, 400), theme=FUTURE_DARK)
    surface = ThemeSurface(bounds=Rect(80, 80, 420, 220),
                           style=SurfaceStyle(kind="glass", depth_layers=2))
    button = Button("Still interactive", bounds=Rect(120, 150, 240, 44))
    surface.add(button)
    root.add(surface)
    mount(window, root)
    driver = AnimationController(app, window)
    effect = SurfaceInteraction(driver, surface)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]

        def frame():
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, height, pixels = context.read_scene_rgba()
            assert width > 0 and len(pixels) == width * height * 4
            assert renderer._contexts[window.native_handle.value] is context
            return bytes(pixels)

        def move(x, y):
            window._apply_platform_event(PlatformEvent(
                PlatformEventKind.POINTER_MOVE, window.native_handle,
                x=x * window.scale, y=y * window.scale,
            ))

        for theme in (FUTURE_DARK, FUTURE_LIGHT):
            root.theme = theme
            move(600, 360)
            driver.tick(1)
            idle = frame()
            move(100, 100)
            driver.tick(theme.motion_duration / 3)
            intermediate = frame()
            driver.tick(1)
            active = frame()
            assert len({idle, intermediate, active}) == 3
            assert effect.progress == 1 and driver.active_count == 0
            assert window.scene.hit_test_xy(200, 170).key == button.key
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("material_motion_frames", "idle/intermediate/hover in dark and light")
    finally:
        effect.dispose()
        driver.dispose()
        app.stop()
