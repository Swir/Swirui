"""Runtime editor colors, rich text and completion popup on a real Windows GPU."""

import sys
from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Autocomplete,
    CodeEditor,
    Panel,
    Window,
    mount,
)
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_editor_and_popup_switch_themes_without_recreating_native_context(record_property):
    editor = CodeEditor(
        'if True:\n    return "hello" # note\n',
        bounds=Rect(20, 20, 500, 240), language="python", font_size=20, show_minimap=True,
    )
    popup = Autocomplete(
        "s", bounds=Rect(550, 20, 280, 44), items=["Silver", "Sky"],
    )
    root = Panel(bounds=Rect(0, 0, 860, 300), theme=FUTURE_DARK).add(editor, popup)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=860, height=300))
    mount(window, root)
    try:
        app.start()
        context = renderer._contexts[window.native_handle.value]
        window.focus_component(popup)
        popup.open_suggestions()
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, window.native_handle, key_code=0x28)
        )
        editor.select(1, 5)
        for theme in (FUTURE_LIGHT, replace(FUTURE_DARK, monospace_family="Consolas")):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, height, rgba = context.read_scene_rgba()
            nodes = {n.key: n for n in window.scene.walk()}

            def pixel(x, y, width=width, rgba=rgba):
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                return tuple(rgba[offset:offset + 3])

            def rgb(role, theme=theme):
                color = theme.text_color(role)
                return tuple(round(c * 255) for c in (color.r, color.g, color.b))

            gutter = nodes[editor.key + ":gutter"]
            assert pixel(gutter.bounds.x + 3, gutter.bounds.y + 80) == pytest.approx(
                rgb("canvas"), abs=1
            )
            minimap = nodes[editor.key + ":minimap:background"]
            assert pixel(minimap.bounds.x + 4, minimap.bounds.bottom - 5) == pytest.approx(
                rgb("canvas"), abs=1
            )
            bucket = nodes[editor.key + ":minimap:bucket:0"]
            mark = pixel(
                bucket.bounds.x + bucket.bounds.width / 2,
                bucket.bounds.y + bucket.bounds.height / 2,
            )
            # Two-pixel marks include SDF antialiasing even at their center.
            # They must be visibly painted above the viewport, near their ink
            # color rather than erased by the selection rectangle.
            ink, backdrop = rgb("muted"), rgb("selection")
            assert sum(abs(a - b) for a, b in zip(mark, ink, strict=True)) < (
                0.35 * sum(abs(a - b) for a, b in zip(backdrop, ink, strict=True))
            )
            selected = nodes[popup.key + ":suggestion:0:selected"]
            assert pixel(selected.bounds.right - 15, selected.bounds.y + 10) == pytest.approx(
                rgb("selection"), abs=1
            )
            unselected = nodes[popup.key + ":suggestion:1"]
            assert pixel(unselected.bounds.right - 5, unselected.bounds.y + 10) == pytest.approx(
                rgb("surface"), abs=1
            )
            first_line = nodes[editor.key + ":text:0"]
            assert first_line.font_family == theme.monospace_family
            assert first_line.text_spans == (
                (0, 1, theme.text_color("accent")), (5, 7, theme.text_color("accent"))
            )
            assert first_line.fill == theme.text_color("text")
            # The selected text stays in its original shaped row, using plain
            # foreground. Unselected syntax still reaches the GPU as rich runs.
            assert not any(":syntax:" in key for key in nodes)
            second_line = nodes[editor.key + ":text:1"]
            color = rgb("success")
            region = second_line.bounds
            assert any(
                all(abs(a - b) <= 1 for a, b in zip(pixel(x, y), color, strict=True))
                for y in range(int(region.y), int(region.bottom))
                for x in range(int(region.x), int(min(region.right, editor.bounds.right - 80)))
            )
            assert popup.value == "s" and popup.selected_suggestion == "Silver"
            assert window.focused_component is popup
            assert renderer._contexts[window.native_handle.value] is context
        record_property("native_rgba_readback", f"{width}x{height}")
        record_property("same_context_theme_switches", 2)
    finally:
        app.stop()
