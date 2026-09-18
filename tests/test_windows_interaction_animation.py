import ctypes
import sys
import time
from collections.abc import Callable
from typing import Any

import pytest

from swirui import (
    AnimationController,
    App,
    Button,
    InteractionAnimator,
    MagneticInteractionAnimator,
    Window,
    mount,
)
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


def _pump_until(app: App, predicate: Callable[[], bool], *, timeout: float = 1.0) -> None:
    """Pump native events until the expected routed state is observable."""

    deadline = time.monotonic() + timeout
    while not predicate():
        app.process_events()
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for routed Win32 interaction state.")
        time.sleep(0.005)


def _render_after_invalidation(
    app: App,
    renderer: WgpuRenderer,
    previous_frames: int,
    *,
    timeout: float = 1.0,
) -> None:
    """Require at least one new presented frame without assuming exact frame counts."""

    deadline = time.monotonic() + timeout
    while renderer.frames_rendered <= previous_frames:
        app.process_events()
        app.render_pending(time.monotonic() + 1.0)
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for the invalidated Win32 GPU frame.")
        time.sleep(0.005)


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
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()
        x = max(1, round(180.0 * window.scale))
        y = max(1, round(110.0 * window.scale))

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0, _lparam(x, y))
        _pump_until(app, lambda: animator.phase.value == "hovered")
        controller.tick(0.10)
        assert button.opacity == pytest.approx(0.96)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        hovered = next(node for node in window.scene.walk() if node.key == "animated-button")
        assert hovered.opacity == pytest.approx(0.96)

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0201, 0x0001, _lparam(x, y))
        _pump_until(app, lambda: animator.phase.value == "pressed")
        controller.tick(0.10)
        assert button.opacity == pytest.approx(0.82)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        pressed = next(node for node in window.scene.walk() if node.key == "animated-button")
        assert pressed.opacity == pytest.approx(0.82)
        assert runtime.generation > 1

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0202, 0, _lparam(x, y))
        _pump_until(app, lambda: animator.phase.value == "hovered")
        controller.tick(0.16)
        assert button.opacity == pytest.approx(0.96)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
    finally:
        animator.dispose()
        controller.dispose()
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="magnetic interaction smoke requires Windows")
def test_real_win32_magnetic_offset_tracks_hit_testing_and_reuses_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI magnetic interaction smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI magnetic interaction", width=520, height=260))
    button = Button(
        "Magnetic",
        key="magnetic-button",
        bounds=Rect(120.0, 86.0, 220.0, 52.0),
    )
    authored_bounds = button.bounds
    runtime = mount(window, button)
    controller = AnimationController(app, window)
    magnetic = MagneticInteractionAnimator(controller, button)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()
        x = max(1, round(315.0 * window.scale))
        y = max(1, round(110.0 * window.scale))

        previous_frames = renderer.frames_rendered
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0, _lparam(x, y))
        _pump_until(app, lambda: magnetic.offset.x > 0.0)
        assert button.bounds == authored_bounds
        assert window.scene is not None
        attracted = next(node for node in window.scene.walk() if node.key == "magnetic-button")
        assert attracted.bounds.x > authored_bounds.x
        assert attracted.bounds.y < authored_bounds.y
        assert window.scene.hit_test_xy(315.0, 110.0) is not None

        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1

        outside_x = max(1, round(20.0 * window.scale))
        outside_y = max(1, round(20.0 * window.scale))
        user32.SendMessageW(
            ctypes.c_void_p(hwnd),
            0x0200,
            0,
            _lparam(outside_x, outside_y),
        )
        _pump_until(app, lambda: magnetic.active)
        previous_frames = renderer.frames_rendered
        controller.tick(2.0)
        assert magnetic.active is False
        assert magnetic.offset.x == pytest.approx(0.0)
        assert magnetic.offset.y == pytest.approx(0.0)
        assert button.bounds == authored_bounds

        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
    finally:
        magnetic.dispose()
        controller.dispose()
        app.stop()
