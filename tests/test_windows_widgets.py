import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import (
    App,
    Checkbox,
    Component,
    Input,
    PasswordInput,
    ProgressBar,
    ProgressRing,
    RangeSlider,
    Slider,
    Switch,
    TextArea,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, SceneNodeKind, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.CoreWidgets.{id(backend):x}"
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


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_retained_text_inputs_route_real_win32_text_and_reuse_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI core widget smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI core widgets", width=620, height=360))
    root = Component("root")
    username = Input(
        key="username",
        bounds=Rect(28.0, 30.0, 280.0, 48.0),
        placeholder="Username",
        accessible_name="Username",
    )
    password = PasswordInput(
        "secret",
        key="password",
        bounds=Rect(28.0, 96.0, 280.0, 48.0),
        accessible_name="Password",
    )
    notes = TextArea(
        "native\nwidgets",
        key="notes",
        bounds=Rect(28.0, 162.0, 420.0, 118.0),
        accessible_name="Notes",
    )
    root.add(username, password, notes)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        app.process_events()
        x = max(1, round(48.0 * window.scale))
        y = max(1, round(50.0 * window.scale))
        _user32().SendMessageW(
            ctypes.c_void_p(window.native_handle.value),
            0x0201,
            0,
            _lparam(x, y),
        )
        app.process_events()
        assert window.focused_component is username

        for character in "SwirUI":
            _user32().SendMessageW(
                ctypes.c_void_p(window.native_handle.value),
                0x0102,
                ord(character),
                0,
            )
        app.process_events()
        assert username.value == "SwirUI"
        assert runtime.generation > 1

        app.invalidate(window)
        rendered = app.render_pending(time.monotonic() + 1.0)
        assert rendered == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        username_text = next(
            node for node in window.scene.walk() if node.key == "username:text"
        )
        password_text = next(
            node for node in window.scene.walk() if node.key == "password:text"
        )
        assert username_text.kind is SceneNodeKind.TEXT
        assert username_text.text == "SwirUI"
        assert password_text.text == "••••••"
        assert password_text.text != password.value
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_retained_toggles_route_real_win32_input_and_reuse_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI toggle smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI retained toggles", width=620, height=300))
    root = Component("root")
    checkbox = Checkbox(
        "Native checkbox",
        key="native-checkbox",
        bounds=Rect(28.0, 34.0, 260.0, 44.0),
    )
    switch = Switch(
        "Native switch",
        key="native-switch",
        bounds=Rect(28.0, 104.0, 260.0, 44.0),
    )
    root.add(checkbox, switch)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        app.process_events()
        _send_click(
            user32,
            hwnd,
            max(1, round(90.0 * window.scale)),
            max(1, round(54.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is checkbox
        assert checkbox.checked is True

        _send_click(
            user32,
            hwnd,
            max(1, round(90.0 * window.scale)),
            max(1, round(124.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is switch
        assert switch.checked is True

        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0100, 0x20, 0)
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0101, 0x20, 0)
        app.process_events()
        assert switch.checked is False
        assert runtime.generation > 1

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        checkbox_mark = next(
            node for node in window.scene.walk() if node.key == "native-checkbox:mark"
        )
        switch_knob = next(
            node for node in window.scene.walk() if node.key == "native-switch:knob"
        )
        assert checkbox_mark.kind is SceneNodeKind.TEXT
        assert switch_knob.kind is SceneNodeKind.RECTANGLE
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_retained_ranges_and_progress_render_in_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI range progress smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI retained ranges", width=680, height=360))
    root = Component("root")
    slider = Slider(
        key="native-slider",
        bounds=Rect(28.0, 34.0, 300.0, 44.0),
        step=5.0,
        accessible_name="Native slider",
    )
    range_slider = RangeSlider(
        key="native-range",
        bounds=Rect(28.0, 104.0, 300.0, 44.0),
        lower_value=20.0,
        upper_value=80.0,
        step=5.0,
        accessible_name="Native range",
    )
    progress = ProgressBar(
        key="native-progress",
        bounds=Rect(28.0, 186.0, 300.0, 14.0),
        value=50.0,
        accessible_name="Native progress",
    )
    ring = ProgressRing(
        key="native-ring",
        bounds=Rect(420.0, 64.0, 112.0, 112.0),
        value=50.0,
        segments=24,
        accessible_name="Native ring",
    )
    root.add(slider, range_slider, progress, ring)
    runtime = mount(window, root)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        hwnd = window.native_handle.value
        user32 = _user32()

        app.process_events()
        _send_click(
            user32,
            hwnd,
            max(1, round(178.0 * window.scale)),
            max(1, round(56.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is slider
        assert slider.value == 50.0

        _send_click(
            user32,
            hwnd,
            max(1, round(291.0 * window.scale)),
            max(1, round(126.0 * window.scale)),
        )
        app.process_events()
        assert window.focused_component is range_slider
        assert range_slider.active_thumb == "upper"
        assert range_slider.upper_value == 90.0

        progress.value = slider.value
        ring.value = slider.value
        assert runtime.generation > 1

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert next(
            node for node in window.scene.walk() if node.key == "native-slider:thumb"
        ).kind is SceneNodeKind.RECTANGLE
        assert next(
            node for node in window.scene.walk() if node.key == "native-range:upper:thumb"
        ).kind is SceneNodeKind.RECTANGLE
        assert next(
            node for node in window.scene.walk() if node.key == "native-progress:fill"
        ).kind is SceneNodeKind.RECTANGLE
        ring_segments = [
            node
            for node in window.scene.walk()
            if node.key.startswith("native-ring:segment:")
        ]
        assert len(ring_segments) == 24
        assert all(node.kind is SceneNodeKind.PATH for node in ring_segments)
    finally:
        app.stop()
