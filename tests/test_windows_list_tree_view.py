import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, ListItem, ListView, TreeNode, TreeView, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend(name: str) -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.{name}.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="ListView native smoke requires Windows")
def test_list_view_virtualization_survives_native_navigation_on_persistent_wgpu() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend("ListView")
    app = App("SwirUI ListView smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI ListView", width=680, height=360))
    items = tuple(
        ListItem(index, f"Item {index}", secondary=f"meta-{index}")
        for index in range(2_000)
    )
    view = ListView(
        items,
        key="native-list",
        bounds=Rect(24.0, 24.0, 520.0, 240.0),
        item_height=30.0,
        selection_mode="multiple",
        accessible_name="Native workload list",
    )
    runtime = mount(window, view)

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
            max(1, round(140.0 * window.scale)),
            max(1, round(69.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is view
        assert view.selected_index == 1
        assert view.selected_item is not None
        assert view.selected_item.key == 1

        _send_key(user32, hwnd, 0x23)
        app.process_events()
        assert view.selected_index == 1_999
        assert view.selected_item is not None
        assert view.selected_item.key == 1_999
        assert view.scroll_offset > 0.0

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        row_nodes = [
            node
            for node in window.scene.walk()
            if node.key.startswith("native-list:row:")
            and node.kind is SceneNodeKind.RECTANGLE
        ]
        assert len(row_nodes) <= 8
        visible_text = {
            node.text
            for node in window.scene.walk()
            if node.kind is SceneNodeKind.TEXT and node.text is not None
        }
        assert "Item 1999" in visible_text
        assert "Item 1" not in visible_text
        assert view.accessibility_snapshot(focused=view).row_count == 2_000
        assert runtime.generation > 1
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="TreeView native smoke requires Windows")
def test_tree_view_native_hierarchy_navigation_keeps_virtualized_wgpu_scene_bounded() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend("TreeView")
    app = App("SwirUI TreeView smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI TreeView", width=680, height=360))
    root = TreeNode(
        "root",
        "Root",
        tuple(TreeNode(f"child-{index}", f"Child {index}") for index in range(1_500)),
    )
    tree = TreeView(
        (root, TreeNode("other", "Other")),
        key="native-tree",
        bounds=Rect(24.0, 24.0, 520.0, 240.0),
        item_height=30.0,
        accessible_name="Native hierarchy tree",
    )
    runtime = mount(window, tree)

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
            max(1, round(140.0 * window.scale)),
            max(1, round(39.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is tree
        assert tree.selected_node is not None
        assert tree.selected_node.key == "root"
        assert "root" not in tree.expanded_keys

        _send_key(user32, hwnd, 0x27)
        app.process_events()
        assert "root" in tree.expanded_keys
        assert len(tree.items) == 1_502

        _send_key(user32, hwnd, 0x27)
        app.process_events()
        assert tree.selected_node is not None
        assert tree.selected_node.key == "child-0"

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        row_nodes = [
            node
            for node in window.scene.walk()
            if node.key.startswith("native-tree:row:")
            and node.kind is SceneNodeKind.RECTANGLE
        ]
        assert len(row_nodes) <= 8
        snapshot = tree.accessibility_snapshot(focused=tree)
        assert snapshot.row_count == 1_502
        assert len(snapshot.children) <= 8

        _send_key(user32, hwnd, 0x25)
        app.process_events()
        assert tree.selected_node is not None
        assert tree.selected_node.key == "root"
        _send_key(user32, hwnd, 0x25)
        app.process_events()
        assert "root" not in tree.expanded_keys
        assert len(tree.items) == 2
        assert runtime.generation > 1
    finally:
        app.stop()
