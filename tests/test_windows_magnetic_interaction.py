import ctypes
import sys
import time
from collections.abc import Callable
from typing import Any

import pytest

from swirui import AnimationController, App, Button, MagneticInteraction, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Point, Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.MagneticInteraction.{id(backend):x}"
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


def _drain_native_events(app: App, *, max_rounds: int = 32) -> None:
    """Drain setup-time Win32 messages before deterministic pointer injection.

    ``ShowWindow`` can leave a real cursor ``WM_MOUSEMOVE`` queued behind a
    synchronous ``SendMessageW`` injection. If both are consumed in one poll,
    that stale move can immediately deactivate the magnetic interaction and make
    this smoke test depend on the hosted runner's cursor position. Draining the
    queue first keeps the real Win32 routing path while removing startup noise.
    """

    for _ in range(max_rounds):
        if app.process_events() == 0:
            return
    pytest.fail("Win32 startup event queue did not settle before magnetic input injection.")


def _pump_until(app: App, predicate: Callable[[], bool], *, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        app.process_events()
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for routed Win32 magnetic interaction state.")
        time.sleep(0.005)


def _render_after_invalidation(
    app: App,
    renderer: WgpuRenderer,
    previous_frames: int,
    *,
    timeout: float = 1.0,
) -> None:
    """Wait for a real GPU frame without assuming animations stay frozen afterward.

    A rendered frame emits ``frame_rendered`` and can legitimately advance an
    active animation controller. Geometry assertions therefore belong immediately
    after the deterministic manual tick, before this helper pumps another frame.
    """

    deadline = time.monotonic() + timeout
    while renderer.frames_rendered <= previous_frames:
        app.process_events()
        app.render_pending(time.monotonic() + 1.0)
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for invalidated Win32 magnetic GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="magnetic interaction smoke requires Windows")
def test_real_win32_pointer_moves_retained_subtree_in_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI magnetic interaction smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI magnetic interaction", width=520, height=260))
    button = Button(
        "Magnetic",
        key="magnetic-button",
        bounds=Rect(120.0, 86.0, 220.0, 52.0),
    )
    runtime = mount(window, button)
    controller = AnimationController(app, window)
    magnetic = MagneticInteraction(controller, button)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()
        inside_x = max(1, round(330.0 * window.scale))
        inside_y = max(1, round(112.0 * window.scale))

        _drain_native_events(app)
        assert window.scene is not None
        logical_x = window.physical_to_logical(float(inside_x))
        logical_y = window.physical_to_logical(float(inside_y))
        target = window.scene.hit_test_xy(logical_x, logical_y)
        assert target is not None
        assert target.key == "magnetic-button"

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0, _lparam(inside_x, inside_y))
        _pump_until(app, lambda: magnetic.active)
        generation_before_move = runtime.generation
        controller.tick(magnetic.spec.max_duration)
        assert button.visual_offset.x > 0.0
        assert abs(button.visual_offset.y) < 1.0
        moved_offset = button.visual_offset
        assert runtime.generation > generation_before_move
        assert window.scene is not None
        moved = next(node for node in window.scene.walk() if node.key == "magnetic-button")
        assert moved.bounds.x == pytest.approx(120.0 + moved_offset.x)
        assert moved.bounds.y == pytest.approx(86.0 + moved_offset.y)
        assert window.scene.hit_test_xy(330.0 + moved_offset.x, 112.0) is moved

        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts

        outside_x = max(1, round(470.0 * window.scale))
        outside_y = inside_y
        generation_before_restore = runtime.generation
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0, _lparam(outside_x, outside_y))
        _pump_until(app, lambda: magnetic.target_offset == Point())
        controller.tick(magnetic.spec.max_duration)
        assert button.visual_offset == Point()
        # process_events() renders pending frames, so the spring may already have
        # rebuilt the retained scene while _pump_until observes the zero target.
        assert runtime.generation > generation_before_restore
        assert window.scene is not None
        restored = next(node for node in window.scene.walk() if node.key == "magnetic-button")
        assert restored.bounds == Rect(120.0, 86.0, 220.0, 52.0)

        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
    finally:
        magnetic.dispose()
        controller.dispose()
        app.stop()
