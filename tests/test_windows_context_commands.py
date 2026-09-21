import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, CommandItem, CommandPalette, ContextMenu, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.ContextCommands.{id(backend):x}"
    return backend


def _user32() -> Any:
    win_dll: Any = ctypes.__dict__["WinDLL"]
    user32: Any = win_dll("user32", use_last_error=True)
    user32.SendMessageW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_ssize_t,
    ]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    return user32


def _lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def _send_click(user32: Any, hwnd: int, x: int, y: int) -> None:
    point = _lparam(x, y)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0201, 0, point)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0202, 0, point)


@pytest.mark.skipif(sys.platform != "win32", reason="Context command smoke requires Windows")
def test_command_palette_native_text_input_keeps_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI command palette smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Command Palette", width=720, height=420))
    palette = CommandPalette(
        (
            CommandItem("open", "Open workspace", "Ctrl+O"),
            CommandItem("grid", "Toggle Grid", "Ctrl+G"),
            CommandItem("export", "Export image", "Ctrl+E"),
        ),
        bounds=Rect(80.0, 60.0, 440.0, 220.0),
        key="native-palette",
        dismiss_on_invoke=False,
    )
    runtime = mount(window, palette)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        _send_click(
            user32,
            hwnd,
            max(1, round(120.0 * window.scale)),
            max(1, round(84.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is palette

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0102, ord("g"), 0)
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0102, ord("r"), 0)
        app.process_events()
        assert palette.query == "gr"
        assert [item.key for item in palette.filtered_items] == ["grid"]

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, 0x0D, 0)
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, 0x0D, 0)
        app.process_events()
        assert palette.active_item is not None
        assert palette.active_item.key == "grid"

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-palette:query" in scene_keys
        assert "native-palette:result:0" in scene_keys
        assert runtime.generation > 1
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Context command smoke requires Windows")
def test_context_menu_native_pointer_keeps_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI context menu smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Context Menu", width=640, height=360))
    menu = ContextMenu(
        (
            CommandItem("copy", "Copy", "Ctrl+C"),
            CommandItem("rename", "Rename", "F2"),
            CommandItem("delete", "Delete", "Del"),
        ),
        bounds=Rect(60.0, 48.0, 260.0, 120.0),
        key="native-context",
        dismiss_on_invoke=False,
    )
    runtime = mount(window, menu)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        _send_click(
            user32,
            hwnd,
            max(1, round(96.0 * window.scale)),
            max(1, round(106.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is menu
        assert menu.active_item is not None
        assert menu.active_item.key == "rename"

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "native-context:item:1" in scene_keys
        assert runtime.generation > 1
    finally:
        app.stop()
