import sys
from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    App,
    Button,
    Input,
    Panel,
    SurfaceStyle,
    ThemePackage,
    ThemeSurface,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Point, Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_custom_surface_package_renders_materials_depth_and_preserves_input(record_property):
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=640, height=420))
    root = Panel(bounds=Rect(0, 0, 640, 420), theme=FUTURE_DARK)
    root.add(Panel(bounds=Rect(70, 60, 270, 250), background=Color(.02, .3, .7)))
    surface = ThemeSurface(bounds=Rect(100, 80, 420, 260))
    field = Input("My own design", bounds=Rect(130, 180, 340, 44))
    button = Button("Create", bounds=Rect(130, 110, 160, 44))
    surface.add(field, button)
    root.add(surface)
    mount(window, root)
    window.focus_component(field)
    field.select(0, 2)
    frames = []
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        for kind in ("solid", "glass", "acrylic"):
            theme = replace(FUTURE_DARK, surface_style=SurfaceStyle(
                kind=kind, depth_layers=3, glow_radius=18, elevation=12, tint_opacity=.55,
            ))
            package = ThemePackage("Own material", {"custom": theme}, "custom")
            root.theme = ThemePackage.loads(package.dumps()).default
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 1)
            width, height, rgba = context.read_scene_rgba()
            frames.append(bytes(rgba))
            backplates = [n for n in window.scene.root.walk() if ":depth:" in n.key]
            assert len(backplates) == 3 and all(n.path.triangle_count > 2 for n in backplates)
            assert renderer.last_path_count == sum(n.path.triangle_count for n in backplates)
            assert renderer.last_backdrop_count == int(kind != "solid")
            assert renderer._contexts[window.native_handle.value] is context
            assert field.value == "My own design" and field.selected_text == "My"
            assert window.focused_component is field
            # Text/background in an interactive control stays on the normal plane.
            offset = (round(113 * window.scale) * width + round(200 * window.scale)) * 4
            expected = root.theme.text_color("accent")
            assert tuple(rgba[offset:offset + 3]) == pytest.approx(
                tuple(round(v * 255) for v in (expected.r, expected.g, expected.b)), abs=1)
            assert window.scene.hit_test(Point(200, 130)).key.startswith(button.key)
        assert len(set(frames)) == 3
        record_property("native_rgba", f"{width}x{height}")
        record_property("styles", "solid/glass/acrylic; 3 backplates; editable foreground")
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_depth_backplate_follows_live_theme_corners_on_gpu(record_property):
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=320, height=240))
    style = SurfaceStyle(depth_layers=1, depth_spacing=24, tilt_x=0, tilt_y=0,
                         elevation=0, border_width=0)
    root = Panel(bounds=Rect(0, 0, 320, 240), theme=FUTURE_DARK)
    root.add(ThemeSurface(bounds=Rect(40, 40, 140, 90), style=style))
    mount(window, root)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        for radius in (0, 28, 0):
            root.theme = replace(FUTURE_DARK, control_radius=radius)
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, frame = context.read_scene_rgba()

            def pixel(x, y, width=width, frame=frame):
                offset = 4 * (round(y * window.scale) * width + round(x * window.scale))
                return bytes(frame[offset:offset + 4])

            # The face ends at y=130. Only the offset backplate reaches y=154.
            background, edge, corner = pixel(203, 151), pixel(120, 151), pixel(188, 151)
            assert edge != background
            assert corner == (background if radius else edge)
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
    finally:
        app.stop()
