import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    AnimationController,
    App,
    Button,
    Panel,
    SurfaceInteraction,
    SurfaceStyle,
    ThemeSurface,
    Window,
    mount,
)
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.rendering import Rect, WgpuRenderer


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
