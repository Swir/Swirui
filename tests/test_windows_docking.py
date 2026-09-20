import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, DockPane, DockWorkspace, Panel, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Docking.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Docking native smoke requires Windows")
def test_docking_native_redock_and_center_activation_keep_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI docking smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI Docking", width=800, height=480))

    explorer = Panel(
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        key="explorer-content",
        accessible_name="Explorer content",
    )
    editor = Panel(
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        key="editor-content",
        accessible_name="Editor content",
    )
    preview = Panel(
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        key="preview-content",
        accessible_name="Preview content",
    )
    workspace = DockWorkspace(
        (
            DockPane("explorer", "Explorer", explorer, dock="left", extent=180.0),
            DockPane("editor", "Editor", editor),
            DockPane("preview", "Preview", preview),
        ),
        bounds=Rect(24.0, 24.0, 620.0, 340.0),
        key="native-dock",
        header_height=36.0,
        accessible_name="Native docking workspace",
    )
    runtime = mount(window, workspace)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        assert workspace.active_center_key == "editor"
        assert editor.visible is True
        assert preview.visible is False

        center = workspace.pane_bounds("editor")
        preview_header_x = center.x + center.width * 0.75
        _send_click(
            user32,
            hwnd,
            max(1, round(preview_header_x * window.scale)),
            max(1, round((center.y + 18.0) * window.scale)),
        )
        app.process_events()
        assert window.focused_component is workspace
        assert workspace.active_center_key == "preview"
        assert editor.visible is False
        assert preview.visible is True

        workspace.dock_pane("explorer", "right", extent=210.0)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert workspace.pane_bounds("explorer").x > workspace.pane_bounds("preview").x

        assert window.scene is not None
        scene_keys = {node.key for node in window.scene.walk()}
        assert "explorer-content" in scene_keys
        assert "preview-content" in scene_keys
        assert "editor-content" not in scene_keys

        snapshot = workspace.accessibility_snapshot(focused=workspace)
        pane_nodes = [
            child
            for child in snapshot.children
            if child.name in {"Explorer", "Editor", "Preview"}
        ]
        assert [child.name for child in pane_nodes] == ["Explorer", "Editor", "Preview"]
        assert any(child.name == "Preview content" for child in snapshot.children)
        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
    finally:
        app.stop()
