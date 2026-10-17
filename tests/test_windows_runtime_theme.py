"""Native pixels and retained state across a live inherited theme switch."""

import sys

import pytest

from swirui import FUTURE_DARK, FUTURE_LIGHT, App, Button, Input, Panel, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_native_theme_switch_recolors_existing_controls_and_retains_focus() -> None:
    root = Panel(bounds=Rect(0, 0, 400, 240), theme=FUTURE_DARK)
    button = Button("Action", bounds=Rect(20, 20, 120, 40))
    field = Input("Keep selection", bounds=Rect(20, 80, 260, 44))
    root.add(button, field)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=400, height=240))
    mount(window, root)
    window.focus_component(field)
    field.select_all()
    try:
        app.start()
        assert window.native_handle is not None
        context = renderer._contexts[window.native_handle.value]

        def sample(x: int, y: int) -> tuple[int, ...]:
            width, _height, pixels = context.read_scene_rgba()
            offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
            return tuple(pixels[offset : offset + 4])

        for theme in (FUTURE_DARK, FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            for x, y, role in ((380, 200, "surface"), (80, 22, "accent")):
                color = theme.text_color(role)
                expected = (round(color.r * 255), round(color.g * 255), round(color.b * 255), 255)
                assert sample(x, y) == pytest.approx(expected, abs=1)
            assert renderer._contexts[window.native_handle.value] is context
            assert root.children == [button, field]
            assert window.focused_component is field
            assert field.selected_text == "Keep selection"
    finally:
        app.stop()
