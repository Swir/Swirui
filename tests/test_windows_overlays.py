import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import App, Button, Component, Modal, ParticleField, Toast, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.Overlays.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="Overlay native smoke requires Windows")
def test_modal_and_toast_share_persistent_win32_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI overlay smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI overlays", width=760, height=460))
    root = Component("root")
    modal = Modal(
        key="native-modal",
        bounds=Rect(0.0, 0.0, 760.0, 460.0),
        dialog_bounds=Rect(190.0, 100.0, 380.0, 230.0),
        content=Button(
            "Confirm",
            key="native-dialog-action",
            bounds=Rect(28.0, 34.0, 160.0, 48.0),
        ),
        accessible_name="Native modal",
    )
    toast = Toast(
        "Native GPU notification surface",
        key="native-toast",
        title="SwirUI",
        bounds=Rect(404.0, 24.0, 320.0, 92.0),
        kind="info",
        duration_seconds=2.0,
    )
    root.add(modal, toast)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        persistent_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        app.process_events()
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0201,
            0x0001,
            _lparam(round(40.0 * window.scale), round(40.0 * window.scale)),
        )
        app.process_events()
        assert modal.is_open is False
        assert runtime.generation > 1

        frame_time = time.monotonic() + 1.0
        app.invalidate(window)
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == persistent_contexts
        assert window.scene is not None
        assert any(
            node.key == "native-toast" and node.kind is SceneNodeKind.RECTANGLE
            for node in window.scene.walk()
        )

        assert modal.show(reason="native-smoke") is True
        assert toast.advance(2.0) is True
        frame_time += 1.0
        app.invalidate(window)
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == persistent_contexts
        assert window.scene is not None
        assert any(
            node.key == "native-modal" and node.kind is SceneNodeKind.RECTANGLE
            for node in window.scene.walk()
        )
        assert not any(node.key == "native-toast" for node in window.scene.walk())
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Particle native smoke requires Windows")
def test_particle_field_animates_on_persistent_win32_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI particle smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI particles", width=720, height=420))
    field = ParticleField(
        key="native-particles",
        bounds=Rect(24.0, 24.0, 672.0, 372.0),
        particle_count=48,
        seed=2026,
        colors=(Color.from_hex("#0088FF"), Color.from_hex("#62E5FF")),
        loop=False,
        duration=1.0,
    )
    runtime = mount(window, field)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.persistent_context_count == 1
        persistent_contexts = renderer.persistent_context_count
        initial_generation = runtime.generation

        field.start()
        field.advance(1.0 / 60.0)
        assert runtime.generation > initial_generation

        frame_time = time.monotonic() + 1.0
        app.invalidate(window)
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == persistent_contexts
        assert renderer.last_rectangle_count > 0
        assert window.scene is not None
        assert any(
            node.kind is SceneNodeKind.RECTANGLE
            and node.key.startswith("native-particles:particle:")
            for node in window.scene.walk()
        )

        field.advance(0.25)
        frame_time += 0.25
        app.invalidate(window)
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == persistent_contexts
        assert renderer.last_rectangle_count > 0
    finally:
        app.stop()
