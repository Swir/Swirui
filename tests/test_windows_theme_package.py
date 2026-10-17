import sys
from pathlib import Path

import pytest

from swirui import App, Button, Input, Panel, ThemePackage, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows/wgpu readback required")
def test_file_package_switches_native_pixels_without_recreating_controls(tmp_path, record_property):
    sample = Path(__file__).resolve().parents[1] / "examples/themes/aurora.swirui-theme.json"
    original = ThemePackage.load(sample)
    target = tmp_path / "installed-theme.json"
    original.save(target)
    loaded = ThemePackage.load(target)
    root = Panel(bounds=Rect(0, 0, 440, 240), theme=loaded.default)
    button = Button("Create", bounds=Rect(20, 20, 160, 44))
    field = Input("Unsaved draft", bounds=Rect(20, 90, 320, 44))
    root.add(button, field)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=440, height=240))
    mount(window, root)
    window.focus_component(field)
    field.select(0, 7)
    try:
        app.start()
        context = renderer._contexts[window.native_handle.value]
        for key in ("night", "day", "night"):
            root.theme = loaded.themes[key]
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, height, rgba = context.read_scene_rgba()
            for x, y, role in ((400, 200, "surface"), (100, 23, "accent")):
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                color = loaded.themes[key].text_color(role)
                assert tuple(rgba[offset:offset + 4]) == pytest.approx(
                    tuple(round(v * 255) for v in (color.r, color.g, color.b, color.a)), abs=1
                )
            assert renderer._contexts[window.native_handle.value] is context
            assert root.children == [button, field]
            assert window.focused_component is field
            assert field.value == "Unsaved draft" and field.selected_text == "Unsaved"
        record_property("native_rgba_readback", f"{width}x{height}")
        record_property("theme_file", sample.name)
    finally:
        app.stop()
