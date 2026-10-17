import sys

import pytest

from swirui import App, CodeEditor, Panel, TextArea, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Affine2D, Color, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native text and wgpu")


@pytest.mark.parametrize("scale", [1, 1.5, 2])
def test_native_color_spans_preserve_shaping_and_opacity(scale):
    import _swirui_native as native

    text = "office AVATAR é😀"
    args = (text, 500, 80, 24 * scale, 1, 1, 1, 1, "Segoe UI")
    plain = bytes(native.rasterize_text_rgba(*args))
    spans = [(0, 2, 1, 0, 0, 1), (3, 6, 0, 1, 0, 1), (8, 10, 0, 0, 1, 1)]
    colored = bytes(native.rasterize_text_rgba(*args, spans=spans))
    assert plain[3::4] == colored[3::4]  # color boundaries do not shift glyphs
    assert colored != plain
    half = bytes(native.rasterize_text_rgba(*args, spans=[(0, len(text), 1, 0, 0, 0.5)]))
    assert max(half[3::4]) == pytest.approx(128, abs=1)
    with pytest.raises(ValueError):
        native.rasterize_text_rgba(*args, spans=[(0, len(text) + 1, 1, 0, 0, 1)])


def test_multiline_caret_and_colored_code_render_in_real_gpu():
    black, white, red = Color(0, 0, 0), Color(1, 1, 1), Color(1, 0, 0)
    area = TextArea(
        "iiiiWW\nWWiiii",
        bounds=Rect(20, 20, 280, 140),
        font_size=24,
        background=black,
        focused_background=black,
        foreground=white,
        caret_color=red,
    )
    editor = CodeEditor(
        "if iii:\n    return 42",
        bounds=Rect(320, 20, 340, 160),
        font_family="Segoe UI",
        font_size=24,
        language="python",
        syntax_colors={"keyword": red},
        foreground=white,
        background=black,
        current_line_background=black,
    )
    root = Panel(bounds=Rect(0, 0, 700, 240), background=black)
    root.add(area, editor)
    renderer = WgpuRenderer(background=black)
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=700, height=240))
    mount(window, root)
    try:
        app.start()
        window.focus_component(area)
        assert window._text_shaper.supports_color_spans
        scheduler = app._frame_schedulers[window]
        app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
        context = renderer._contexts[window.native_handle.value]
        width, height, rgba = context.read_scene_rgba()

        def colored_pixels(rect, channel):
            return [
                (x, y)
                for y in range(round(rect.y), round(rect.bottom))
                for x in range(round(rect.x), round(rect.right))
                if rgba[(y * width + x) * 4 + channel] > 180
                and rgba[(y * width + x) * 4 + (channel + 1) % 3] < 40
            ]

        scale = window.scale
        caret = next(n for n in window.scene.walk() if n.key == area.key + ":caret")
        red_caret = colored_pixels(Rect(20 * scale, 60 * scale, 280 * scale, 40 * scale), 0)
        assert red_caret and min(x for x, _ in red_caret) == pytest.approx(
            caret.bounds.x * scale, abs=1
        )
        code_line = next(n for n in window.scene.walk() if n.key == editor.key + ":text:0")
        assert code_line.text_spans
        assert not any(":syntax:" in n.key for n in window.scene.walk())
        red_keyword = colored_pixels(
            Rect(code_line.bounds.x * scale, 30 * scale, 20 * scale, 30 * scale), 0
        )
        assert red_keyword
        # Reuse the live context to exercise arbitrary-affine rich rasterization.
        node = SceneNode(
            key="rich",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(60, 60, 260, 48),
            text="AVATAR office",
            font_size=28,
            fill=white,
            text_spans=((0, 6, red), (7, 13, Color(0, 1, 0))),
            transform=Affine2D.rotation(0.15),
        )
        window.set_scene(Scene(700, 240, node))
        app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
        width, height, rgba = context.read_scene_rgba()
        assert colored_pixels(Rect(0, 0, width, height), 0)
        assert colored_pixels(Rect(0, 0, width, height), 1)
        assert renderer.affine_text_cache_size == 1
    finally:
        app.stop()
