import ctypes
import sys
from typing import Any

import pytest

from swirui import App, Component, Window
from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    CornerRadius,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MinMaxInfo(ctypes.Structure):
    _fields_ = [
        ("ptReserved", _Point),
        ("ptMaxSize", _Point),
        ("ptMaxPosition", _Point),
        ("ptMinTrackSize", _Point),
        ("ptMaxTrackSize", _Point),
    ]


def _isolated_backend(label: str) -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Gate02.{label}.{id(backend):x}"
    return backend


def _checker_rgba() -> bytes:
    return bytes(
        [
            0,
            140,
            255,
            255,
            122,
            46,
            255,
            255,
            122,
            46,
            255,
            255,
            0,
            140,
            255,
            255,
        ]
    )


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


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 client-area smoke requires Windows")
def test_win32_sizes_the_renderable_client_area_exactly_and_enforces_minimums() -> None:
    backend = _isolated_backend("client")
    backend.initialize()
    handle = backend.create_window(
        NativeWindowSpec(
            "SwirUI exact client smoke",
            640,
            420,
            min_width=420,
            min_height=280,
        )
    )

    try:
        assert backend.client_size(handle) == (640, 420)
        backend.resize_window(handle, 713, 467)
        assert backend.client_size(handle) == (713, 467)

        info = _MinMaxInfo()
        _user32().SendMessageW(
            ctypes.c_void_p(handle.value),
            0x0024,
            0,
            ctypes.addressof(info),
        )
        assert info.ptMinTrackSize.x >= 420
        assert info.ptMinTrackSize.y >= 280
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="0.2 native milestone gate requires Windows")
def test_02_gate_renders_mixed_gpu_scene_resizes_exactly_and_routes_native_input() -> None:
    root_component = Component("root", key="root")
    action_component = Component("action", key="action", focusable=True)
    root_component.add(action_component)

    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 680, 440))
    panel = SceneNode(
        "panel",
        SceneNodeKind.GROUP,
        Rect(30, 30, 620, 380),
        fill=Color.from_hex("#101B30"),
        corner_radius=CornerRadius.uniform(28),
        clip_to_bounds=True,
    )
    panel.add(
        SceneNode(
            "action",
            SceneNodeKind.RECTANGLE,
            Rect(56, 60, 210, 90),
            fill=Color.from_hex("#008CFF"),
            corner_radius=CornerRadius.uniform(20),
        ),
        SceneNode(
            "title",
            SceneNodeKind.TEXT,
            Rect(82, 82, 300, 54),
            text="SwirUI 0.2 native gate ✓",
            fill=Color.from_hex("#FFFFFF"),
            font_size=24,
            font_family="Segoe UI",
        ),
        SceneNode(
            "image",
            SceneNodeKind.IMAGE,
            Rect(360, 64, 190, 130),
            resource_id="gate-checker",
            opacity=0.92,
        ),
        SceneNode(
            "path",
            SceneNodeKind.PATH,
            Rect(84, 205, 260, 145),
            fill=Color.from_hex("#7A2EFF"),
            path=Path2D.polygon(
                Point(0, 0),
                Point(260, 0),
                Point(260, 58),
                Point(130, 58),
                Point(130, 145),
                Point(0, 145),
            ),
            opacity=0.88,
        ),
    )
    root.add(panel)

    renderer = WgpuRenderer()
    renderer.register_image_rgba("gate-checker", 2, 2, _checker_rgba())
    backend = _isolated_backend("integrated")
    app = App("SwirUI 0.2 integrated gate", platform_backend=backend, renderer=renderer)
    window = Window(title="SwirUI 0.2 gate", width=680, height=440)
    window.set_root(root_component)
    window.set_scene(Scene(680, 440, root))
    app.add_window(window)

    received: list[str] = []
    action_component.on("pointer_down", lambda _event: received.append("pointer_down"))

    try:
        app.start()
        assert window.native_handle is not None
        assert backend.client_size(window.native_handle) == window.pixel_size
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 2
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 1
        assert renderer.last_path_count == 4
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend

        # Drain creation/show messages before injecting the input assertion. Use
        # an uncovered portion of the action rectangle so the later title node
        # cannot legitimately win painter-order hit testing.
        app.process_events()
        x = max(1, round(70 * window.scale))
        y = max(1, round(75 * window.scale))
        lparam = (y << 16) | x
        _user32().SendMessageW(
            ctypes.c_void_p(window.native_handle.value),
            0x0201,
            0,
            lparam,
        )
        app.process_events()
        assert received == ["pointer_down"]
        assert window.focused_component is action_component

        window.resize(720, 480)
        assert backend.client_size(window.native_handle) == window.pixel_size
        app.process_events()
        assert renderer.persistent_context_count == 1
        assert renderer.last_rectangle_count == 2
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 1
        assert renderer.last_path_count == 4
    finally:
        app.stop()
