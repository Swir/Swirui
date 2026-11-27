import ctypes
import sys
import time
from typing import Any

import pytest

from swirui import (
    FUTURE_DARK,
    App,
    Badge,
    Checkbox,
    Chip,
    Component,
    GlassCard,
    Input,
    Label,
    PasswordInput,
    ProgressBar,
    ProgressRing,
    RangeSlider,
    Slider,
    Switch,
    TextArea,
    Tooltip,
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


def _dispatch_sent_messages(app):
    # A synchronous test input need not coincide with the physical desktop cursor.
    events = app.platform_backend._events
    while events:
        app._dispatch_platform_event(events.popleft())


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 capture and wgpu readback required")
def test_tab_distinguishes_coincident_range_handles_on_the_gpu() -> None:
    app = App(platform_backend=_isolated_backend(), renderer=WgpuRenderer())
    window = app.add_window(Window(width=420, height=240))
    slider = RangeSlider(bounds=Rect(30, 50, 300, 44), lower_value=50, upper_value=50,
                         theme=FUTURE_DARK, step=10)
    after = Slider(bounds=Rect(30, 140, 300, 44))
    root = Component()
    root.add(slider, after)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        hwnd = window.native_handle.value
        context = app.renderer._contexts[hwnd]
        user32 = _user32()

        def press(key):
            user32.SendMessageW(hwnd, 0x0100, key, 1)  # WM_KEYDOWN
            user32.SendMessageW(hwnd, 0x0101, key, 1)  # WM_KEYUP
            app.process_events()
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)

        def center_pixels():
            width, _, rgba = context.read_scene_rgba()
            x1, x2 = round(176 * window.scale), round(184 * window.scale)
            y1, y2 = round(68 * window.scale), round(76 * window.scale)
            return b"".join(rgba[4 * (y * width + x1):4 * (y * width + x2)]
                            for y in range(y1, y2))

        press(0x09)
        assert window.focused_component is slider and slider.active_thumb == "lower"
        lower = center_pixels()
        press(0x09)
        assert window.focused_component is slider and slider.active_thumb == "upper"
        upper = center_pixels()
        assert (slider.lower_value, slider.upper_value) == (50, 50)
        assert sum(abs(a - b) > 32 for a, b in zip(lower, upper, strict=True)) >= 6
        press(0x27)  # Right
        assert (slider.lower_value, slider.upper_value) == (50, 60)
        press(0x09)
        assert window.focused_component is after
        assert app.renderer._contexts[hwnd] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 capture and wgpu readback required")
def test_slider_drag_updates_gpu_track_outside_the_client_and_releases_capture() -> None:
    renderer = WgpuRenderer()
    app = App(platform_backend=_isolated_backend(), renderer=renderer)
    window = app.add_window(Window(width=420, height=240))
    single = Slider(bounds=Rect(20, 24, 250, 40), maximum=10, step=3, value=6)
    interval = RangeSlider(bounds=Rect(20, 96, 250, 40), maximum=10, step=3,
                           lower_value=0, upper_value=6)
    root = Component("ranges")
    root.add(single, interval)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        hwnd = window.native_handle.value
        user32 = _user32()
        user32.GetCapture.argtypes, user32.GetCapture.restype = [], ctypes.c_void_p
        context = renderer._contexts[hwnd]

        def mouse(message, flags, x, y):
            point = _lparam(round(x * window.scale), round(y * window.scale))
            user32.SendMessageW(hwnd, message, flags, point)
            _dispatch_sent_messages(app)

        def track_pixels(y):
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, frame = context.read_scene_rgba()
            row = round(y * window.scale) * width
            offsets = [4 * (row + round(x * window.scale)) for x in (80, 225)]
            return tuple(bytes(frame[i:i + 3]) for i in offsets)

        for slider in (single, interval):
            y = slider.bounds.y + slider.bounds.height / 2
            filled, empty = track_pixels(y)
            assert filled != empty
            mouse(0x0201, 1, 168, y)  # WM_LBUTTONDOWN on the thumb
            assert user32.GetCapture() == hwnd and window.pointer_capture_component is slider
            mouse(0x0200, 1, 460, -30)  # WM_MOUSEMOVE above and beyond the client
            assert (slider.value if slider is single else interval.upper_value) == 10
            assert track_pixels(y) == (filled, filled)
            mouse(0x0202, 0, -30, -30)  # WM_LBUTTONUP at the opposite end
            assert not user32.GetCapture() and window.pointer_capture_component is None
            assert (slider.value if slider is single else interval.upper_value) == 0
            assert track_pixels(y) == (empty, empty)
        assert interval.lower_value == 0 and interval.active_thumb == "upper"

        # Reopen a shared handle in either direction through native pointer capture.
        interval.upper_value = 6
        interval.lower_value = 6
        y = interval.bounds.y + interval.bounds.height / 2
        assert track_pixels(y) == (empty, empty)
        mouse(0x0201, 1, 163, y)
        mouse(0x0200, 1, 350, y)
        assert (interval.lower_value, interval.upper_value) == (6, 10)
        assert track_pixels(y) == (empty, filled)
        mouse(0x0202, 0, 25, y)
        assert (interval.lower_value, interval.upper_value) == (6, 6)
        assert not user32.GetCapture()
        mouse(0x0201, 1, 173, y)
        mouse(0x0200, 1, 20, y)
        assert (interval.lower_value, interval.upper_value) == (0, 6)
        assert track_pixels(y) == (filled, empty)
        mouse(0x0202, 0, 20, y)
        assert not user32.GetCapture() and renderer._contexts[hwnd] is context
    finally:
        app.stop()


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


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_retained_content_surfaces_and_tooltip_reuse_real_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI surface widget smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI retained surfaces", width=720, height=380))
    root = Component("root")
    glass = GlassCard(
        key="native-glass",
        bounds=Rect(24.0, 24.0, 440.0, 250.0),
        accessible_name="Native glass card",
    )
    title = Label(
        "Persistent GPU surface",
        key="native-glass-title",
        bounds=Rect(48.0, 48.0, 280.0, 30.0),
    )
    chip = Chip(
        "GPU active",
        key="native-chip",
        bounds=Rect(48.0, 96.0, 150.0, 40.0),
        accessible_name="GPU active",
    )
    badge = Badge(
        "retained",
        key="native-badge",
        bounds=Rect(48.0, 158.0, 104.0, 28.0),
    )
    glass.add(title, chip, badge)
    tooltip = Tooltip(
        "Toggle retained state",
        key="native-tooltip",
        target=chip,
        bounds=Rect(216.0, 98.0, 190.0, 36.0),
    )
    root.add(glass, tooltip)
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
        x = max(1, round(90.0 * window.scale))
        y = max(1, round(116.0 * window.scale))
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0200, 0, _lparam(x, y))
        _dispatch_sent_messages(app)
        assert tooltip.is_open is True
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x02A3, 0, 0)
        _dispatch_sent_messages(app)
        assert not tooltip.is_open

        _send_click(user32, hwnd, x, y)
        app.process_events()
        assert window.focused_component is chip
        assert chip.selected is True
        assert tooltip.is_open is True
        assert runtime.generation > 1

        app.invalidate(window)
        frame_time = time.monotonic() + 1.0
        assert app.render_pending(frame_time) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        assert next(
            node for node in window.scene.walk() if node.key == "native-glass"
        ).kind is SceneNodeKind.BACKDROP_BLUR
        assert next(
            node for node in window.scene.walk() if node.key == "native-chip"
        ).kind is SceneNodeKind.RECTANGLE
        assert next(
            node for node in window.scene.walk() if node.key == "native-badge"
        ).kind is SceneNodeKind.RECTANGLE
        assert next(
            node for node in window.scene.walk() if node.key == "native-tooltip"
        ).kind is SceneNodeKind.RECTANGLE
    finally:
        app.stop()
