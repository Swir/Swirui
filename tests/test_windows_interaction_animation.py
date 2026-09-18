import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import AnimationController, App, Button, InteractionAnimator, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.InteractionAnimation.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="interaction animation smoke requires Windows")
def test_real_win32_pointer_animates_retained_button_in_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI interaction animation smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI interaction animation", width=520, height=260))
    button = Button(
        "Animate",
        key="animated-button",
        bounds=Rect(120.0, 86.0, 220.0, 52.0),
    )
    runtime = mount(window, button)
    controller = AnimationController(app, window)
    animator = InteractionAnimator(controller, button)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()
        x = max(1, round(180.0 * window.scale))
        y = max(1, round(110.0 * window.scale))

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0, _lparam(x, y))
        app.process_events()
        assert animator.phase.value == "hovered"
        controller.tick(0.10)
        assert button.opacity == pytest.approx(0.96)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        hovered = next(node for node in window.scene.walk() if node.key == "animated-button")
        assert hovered.opacity == pytest.approx(0.96)

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0201, 0, _lparam(x, y))
        app.process_events()
        assert animator.phase.value == "pressed"
        controller.tick(0.10)
        assert button.opacity == pytest.approx(0.82)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        pressed = next(node for node in window.scene.walk() if node.key == "animated-button")
        assert pressed.opacity == pytest.approx(0.82)
        assert runtime.generation > 1

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0202, 0, _lparam(x, y))
        app.process_events()
        controller.tick(0.16)
        assert button.opacity == pytest.approx(0.96)
        assert renderer.persistent_context_count == initial_contexts
    finally:
        animator.dispose()
        controller.dispose()
        app.stop()
