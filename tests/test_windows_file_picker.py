import ctypes
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from swirui import App, FileFilter, FilePicker, Panel, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.FilePicker.{id(backend):x}"
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


def _send_key(user32: Any, hwnd: int, key_code: int) -> None:
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, key_code, 0)
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, key_code, 0)


@pytest.mark.skipif(sys.platform != "win32", reason="File picker smoke requires Windows")
def test_file_picker_native_input_keeps_persistent_wgpu_context() -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        directory = Path(temp_directory)
        (directory / "folder").mkdir()
        selected_file = directory / "sample.txt"
        selected_file.write_text("SwirUI", encoding="utf-8")

        renderer = WgpuRenderer()
        backend = _isolated_backend()
        app = App("SwirUI file picker smoke", platform_backend=backend, renderer=renderer)
        window = app.add_window(Window(title="SwirUI File Picker", width=780, height=520))
        picker = FilePicker(
            bounds=Rect(70.0, 60.0, 640.0, 390.0),
            directory=directory,
            filters=(FileFilter("Text", ("*.txt",)),),
            key="native-file-picker",
        )
        confirmed: list[Path] = []
        picker.on("selection_confirmed", lambda event: confirmed.append(event.data["path"]))
        root = Panel(bounds=Rect(0.0, 0.0, 780.0, 520.0), key="file-picker-root")
        root.add(picker)
        runtime = mount(window, root)

        try:
            app.start()
            assert window.native_handle is not None
            assert renderer.frames_rendered == 1
            assert renderer.persistent_context_count == 1
            initial_contexts = renderer.persistent_context_count
            hwnd = window.native_handle.value
            user32 = _user32()

            file_index = next(
                index for index, entry in enumerate(picker.entries) if not entry.is_directory
            )
            row = picker.row_bounds(file_index)
            _send_click(
                user32,
                hwnd,
                round((row.x + 110.0) * window.scale),
                round((row.y + row.height * 0.5) * window.scale),
            )
            app.process_events()
            assert window.focused_component is picker
            assert picker.selected_path == selected_file.absolute()

            _send_key(user32, hwnd, 0x0D)
            app.process_events()
            assert confirmed == [selected_file.absolute()]

            app.invalidate(window)
            assert app.render_pending(time.monotonic() + 1.0) == 1
            assert renderer.persistent_context_count == initial_contexts
            assert window.scene is not None
            scene_keys = {node.key for node in window.scene.walk()}
            assert "native-file-picker:header" in scene_keys
            assert "native-file-picker:action" in scene_keys
            assert any(key.startswith("native-file-picker:row:") for key in scene_keys)
            assert runtime.generation > 1
        finally:
            app.stop()
