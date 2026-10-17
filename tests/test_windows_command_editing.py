"""Native pixels for editable command queries and fractional result scrolling."""

import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    CommandItem,
    CommandPalette,
    MemoryClipboard,
    Modal,
    Panel,
    Window,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_query_selection_scrollbar_and_header_clipping_in_native_dialog():
    palette = CommandPalette(
        [CommandItem(i, f"Action {i}") for i in range(100)],
        bounds=Rect(0, 0, 440, 288),
        dismiss_on_invoke=False,
    )
    root = Panel(bounds=Rect(0, 0, 800, 500), theme=FUTURE_DARK)
    root.add(Modal(bounds=root.bounds, dialog_bounds=Rect(160, 100, 440, 288), content=palette))
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=800, height=500, clipboard=MemoryClipboard("Action")))
    mount(window, root)
    try:
        app.start()
        assert window.native_handle is not None
        context = renderer._contexts[window.native_handle.value]
        window.focus_component(palette)
        for code in (0x56, 0x41):
            window._apply_platform_event(
                PlatformEvent(
                    PlatformEventKind.KEY_DOWN,
                    NativeWindowHandle(window.native_handle.value),
                    key_code=code,
                    ctrl=True,
                )
            )
        palette.scroll_by(20.5)
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, _height, pixels = context.read_scene_rgba()
            for x, y, role in ((176, 131, "selection"), (460, 140, "raised"), (594, 156, "accent")):
                expected = theme.text_color(role)
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                assert tuple(pixels[offset : offset + 3]) == pytest.approx(
                    (round(expected.r * 255), round(expected.g * 255), round(expected.b * 255)),
                    abs=1,
                ), (x, y, role)
            assert (
                palette.query == palette.selected_text == "Action" and palette.scroll_offset == 20.5
            )
            assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()
