import ctypes
import sys
import time
from collections.abc import Callable
from ctypes.wintypes import RECT
from typing import Any

import pytest

from swirui import AnimationController, App, Button, MagneticInteraction, Window, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Point, Rect, WgpuRenderer


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


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
    user32.GetCursorPos.argtypes = [ctypes.POINTER(_Point)]
    user32.GetCursorPos.restype = ctypes.c_bool
    user32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Point)]
    user32.ClientToScreen.restype = ctypes.c_bool
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = ctypes.c_bool
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = ctypes.c_int
    user32.WindowFromPoint.argtypes = [_Point]
    user32.WindowFromPoint.restype = ctypes.c_void_p
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    return user32


def _lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def _cursor_position(user32: Any) -> tuple[int, int]:
    point = _Point()
    if not user32.GetCursorPos(ctypes.byref(point)):
        pytest.fail("GetCursorPos failed before Win32 magnetic input injection.")
    return (int(point.x), int(point.y))


def _screen_point(user32: Any, hwnd: int, x: int, y: int) -> _Point:
    point = _Point(x, y)
    if not user32.ClientToScreen(ctypes.c_void_p(hwnd), ctypes.byref(point)):
        pytest.fail("ClientToScreen failed for Win32 magnetic input injection.")
    return point


def _expose_test_window(
    user32: Any, window: Window, points: tuple[tuple[int, int], ...],
) -> None:
    """Keep both ends of the real mouse gesture visible under desktop overlays."""
    assert window.native_handle is not None
    hwnd = window.native_handle.value
    display = window.display
    assert display is not None
    assert display.work_width is not None and display.work_height is not None
    rect = RECT()
    assert user32.GetWindowRect(hwnd, ctypes.byref(rect))
    left, top = display.work_x, display.work_y
    right = left + max(0, display.work_width - (rect.right - rect.left))
    bottom = top + max(0, display.work_height - (rect.bottom - rect.top))
    positions = ((rect.left, rect.top), (left, top), (right, top), (left, bottom), (right, bottom))
    for x, y in positions:
        # HWND_TOPMOST, SWP_NOSIZE | SWP_NOACTIVATE. Only move our temporary window.
        assert user32.SetWindowPos(hwnd, -1, x, y, 0, 0, 0x0011)
        if all(user32.WindowFromPoint(_screen_point(user32, hwnd, *p)) == hwnd for p in points):
            return
    pytest.fail("No visible position for the two magnetic hover test points.")


def _place_cursor_in_client(user32: Any, hwnd: int, x: int, y: int) -> None:
    """Move the system pointer onto a visible point in the test window."""
    point = _screen_point(user32, hwnd, x, y)
    assert user32.WindowFromPoint(point) == hwnd, "The magnetic test window is covered."
    if not user32.SetCursorPos(int(point.x), int(point.y)):
        pytest.fail("SetCursorPos failed for Win32 magnetic input injection.")


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
    user32: Any | None = None
    original_cursor: tuple[int, int] | None = None

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()
        original_cursor = _cursor_position(user32)
        inside_x = max(1, round(330.0 * window.scale))
        inside_y = max(1, round(112.0 * window.scale))
        outside_x = max(1, round(470.0 * window.scale))
        _expose_test_window(user32, window, ((inside_x, inside_y), (outside_x, inside_y)))
        _place_cursor_in_client(user32, hwnd, outside_x, inside_y)
        _drain_native_events(app)
        controller.tick(magnetic.spec.max_duration)
        assert button.visual_offset == Point() and not magnetic.active
        context = renderer._contexts[hwnd]

        def edge_pixel():
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            offset = 4 * (round(112 * window.scale) * width + round(124 * window.scale))
            return rgba[offset:offset + 3]

        idle_edge = edge_pixel()
        assert window.scene is not None
        logical_x = window.physical_to_logical(float(inside_x))
        logical_y = window.physical_to_logical(float(inside_y))
        target = window.scene.hit_test_xy(logical_x, logical_y)
        assert target is not None
        assert target.key == "magnetic-button"

        _place_cursor_in_client(user32, hwnd, inside_x, inside_y)
        _pump_until(app, lambda: magnetic.active and magnetic.target_offset.x > 0)
        for _ in range(16):
            user32.SendMessageW(hwnd, 0x0200, 0, _lparam(inside_x, inside_y))
        app.process_events()
        assert controller.active_count == 1
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
        assert edge_pixel() != idle_edge

        generation_before_restore = runtime.generation
        _place_cursor_in_client(user32, hwnd, outside_x, inside_y)
        _pump_until(app, lambda: magnetic.target_offset == Point())
        controller.tick(magnetic.spec.max_duration)
        assert button.visual_offset == Point()
        assert runtime.generation > generation_before_restore
        assert window.scene is not None
        restored = next(node for node in window.scene.walk() if node.key == "magnetic-button")
        assert restored.bounds == Rect(120.0, 86.0, 220.0, 52.0)

        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert edge_pixel() == idle_edge and renderer._contexts[hwnd] is context
    finally:
        magnetic.dispose()
        controller.dispose()
        try:
            app.stop()
        finally:
            if user32 is not None and original_cursor is not None:
                user32.SetCursorPos(*original_cursor)
