"""Command surface colors and overflow selection in a real Windows GPU scene."""

import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    CommandItem,
    CommandPalette,
    ContextMenu,
    MenuBar,
    Panel,
    Ribbon,
    RibbonGroup,
    Toolbar,
    Window,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_command_themes_and_overflow_selection_use_same_native_context():
    items = [CommandItem(i, f"Action {i}") for i in range(1000)]
    menu = MenuBar(items, bounds=Rect(20, 20, 540, 40))
    toolbar = Toolbar(items, bounds=Rect(20, 80, 540, 64))
    ribbon = Ribbon([RibbonGroup("home", "Home", items)], bounds=Rect(20, 164, 540, 118))
    context_menu = ContextMenu(items, bounds=Rect(600, 20, 360, 152))
    palette = CommandPalette(items, bounds=Rect(600, 200, 360, 368))
    root = Panel(bounds=Rect(0, 0, 1000, 600), theme=FUTURE_DARK)
    root.add(menu, toolbar, ribbon, context_menu, palette)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=1000, height=600))
    mount(window, root)
    try:
        app.start()
        assert window.native_handle is not None
        context = renderer._contexts[window.native_handle.value]
        for control in (menu, toolbar, context_menu, palette):
            window.focus_component(control)
            window._apply_platform_event(
                PlatformEvent(
                    PlatformEventKind.KEY_DOWN,
                    NativeWindowHandle(window.native_handle.value),
                    key_code=0x23,
                )
            )
            assert control.active_item.key == 999
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, _height, pixels = context.read_scene_rgba()
            for x, y, role in (
                (400, 23, "selection"),
                (460, 83, "selection"),
                (50, 167, "selection"),
                (50, 201, "selection"),
                (900, 137, "selection"),
                (900, 205, "raised"),
                (900, 532, "selection"),
                (601, 300, "focus"),
            ):
                color = theme.text_color(role)
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                assert tuple(pixels[offset : offset + 3]) == pytest.approx(
                    (round(color.r * 255), round(color.g * 255), round(color.b * 255)), abs=1
                ), (x, y, role)
            assert window.focused_component is palette and palette.active_item.key == 999
            assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()
