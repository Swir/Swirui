import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    DockPane,
    DockWorkspace,
    Inspector,
    PropertyItem,
    Terminal,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu readback required")
def test_docked_inspector_and_old_terminal_output_follow_native_theme(record_property):
    inspector = Inspector([PropertyItem("name", "Name", "Draft")], bounds=Rect(0, 0, 1, 1))
    terminal = Terminal(bounds=Rect(0, 0, 1, 1), font_size=22)
    terminal.writeln("plain \x1b[31mRED\x1b[39m normal")
    terminal.input_text = "draft"
    root = DockWorkspace([
        DockPane("properties", "Properties", inspector, dock="left", extent=320),
        DockPane("console", "Console", terminal),
    ], bounds=Rect(0, 0, 900, 420), theme=FUTURE_DARK)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=900, height=420))
    mount(window, root)
    try:
        app.start()
        context = renderer._contexts[window.native_handle.value]
        inspector.begin_edit("name").set_edit_buffer("Unsaved")
        window.focus_component(terminal)
        for theme, red in ((FUTURE_LIGHT, "#A9273D"), (FUTURE_DARK, "#FF7B72")):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, height, rgba = context.read_scene_rgba()
            nodes = {n.key: n for n in window.scene.walk()}

            def pixel(x, y, width=width, rgba=rgba):
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                return tuple(rgba[offset:offset + 3])

            surface = theme.text_color("surface")
            assert pixel(850, 210) == pytest.approx(
                tuple(round(c * 255) for c in (surface.r, surface.g, surface.b)), abs=1
            )
            selected = nodes[inspector.key + ":row:0"]
            selection = theme.text_color("selection")
            assert pixel(selected.bounds.x + 70, selected.bounds.bottom - 4) == pytest.approx(
                tuple(round(c * 255) for c in (selection.r, selection.g, selection.b)), abs=1
            )
            run = next(n for n in nodes.values() if n.text == "RED")
            c = Color.from_hex(red)
            expected = tuple(round(v * 255) for v in (c.r, c.g, c.b))
            assert any(
                all(abs(a - b) <= 1 for a, b in zip(pixel(x, y), expected, strict=True))
                for x in range(int(run.bounds.x), int(run.bounds.x + 50))
                for y in range(int(run.bounds.y), int(run.bounds.bottom))
            )
            assert terminal.input_text == "draft" and inspector.edit_buffer == "Unsaved"
            assert window.focused_component is terminal
            assert renderer._contexts[window.native_handle.value] is context
        record_property("native_rgba_readback", f"{width}x{height}")
    finally:
        app.stop()
