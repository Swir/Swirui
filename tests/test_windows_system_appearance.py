import ctypes
import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Button,
    ColorScheme,
    Input,
    Panel,
    ThemeController,
    ThemeMode,
    Window,
    mount,
)
from swirui.platforms import PlatformEventKind
from swirui.platforms.windows import Win32PlatformBackend
from swirui.platforms.windows_appearance import read_app_color_scheme
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_native_setting_messages_sync_theme_and_preserve_manual_override(
    monkeypatch, record_property,
):
    actual = read_app_color_scheme()
    backend = Win32PlatformBackend()
    renderer = WgpuRenderer()
    app = App(platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(width=480, height=260))
    root = Panel(bounds=Rect(0, 0, 480, 260))
    field = Input("Keep draft", bounds=Rect(20, 100, 300, 44))
    root.add(Button("Create", bounds=Rect(20, 20, 180, 44)), field)
    mount(window, root)
    controller = ThemeController(window)
    window.focus_component(field)
    field.select(0, 4)
    events = []
    window.on("system_appearance_changed", events.append)
    try:
        app.start()
        assert controller.system_scheme is actual
        assert root.theme is (FUTURE_LIGHT if actual is ColorScheme.LIGHT else FUTURE_DARK)
        context = renderer._contexts[window.native_handle.value]
        app.process_events()
        send = backend._user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t
        controlled = [ColorScheme.LIGHT]
        reads = []

        def preference():
            reads.append(controlled[0])
            return controlled[0]

        monkeypatch.setattr("swirui.platforms.windows.read_app_color_scheme", preference)

        def change(scheme, message):
            controlled[0] = scheme
            count = len(reads)
            assert send(ctypes.c_void_p(window.native_handle.value), message, 0, 0) == 0
            assert len(reads) == count  # Query is outside the native callback.
            app.process_events()
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, height, rgba = context.read_scene_rgba()
            theme = controller.effective_theme
            for x, y, role in ((450, 210, "surface"), (100, 23, "accent")):
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                color = theme.text_color(role)
                assert tuple(rgba[offset:offset + 4]) == pytest.approx(
                    tuple(round(v * 255) for v in (color.r, color.g, color.b, color.a)), abs=1)
            assert field.value == "Keep draft" and field.selected_text == "Keep"
            assert window.focused_component is field
            assert renderer._contexts[window.native_handle.value] is context
            assert events[-1].data["event"].kind is PlatformEventKind.SYSTEM_APPEARANCE_CHANGED
            return width, height

        change(ColorScheme.LIGHT, 0x001A)  # WM_SETTINGCHANGE to our own HWND only.
        assert root.theme is FUTURE_LIGHT
        width, height = change(ColorScheme.DARK, 0x031A)  # WM_THEMECHANGED.
        assert root.theme is FUTURE_DARK
        controller.mode = ThemeMode.LIGHT
        change(ColorScheme.DARK, 0x001A)
        assert root.theme is FUTURE_LIGHT and controller.system_scheme is ColorScheme.DARK
        controller.mode = ThemeMode.SYSTEM
        assert root.theme is FUTURE_DARK
        record_property("native_rgba_readback", f"{width}x{height}")
        record_property("actual_initial_app_preference", str(actual))
        record_property("change_source", "Controlled reader + real HWND messages; no OS writes")
    finally:
        app.stop()
    assert controller.closed
