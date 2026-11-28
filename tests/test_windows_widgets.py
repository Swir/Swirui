import ctypes
import math
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
from swirui.rendering import (
    Color,
    GradientStop,
    LinearGradient,
    Point,
    Rect,
    SceneNodeKind,
    WgpuRenderer,
)


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

        context = renderer._contexts[hwnd]
        progress.fill_gradient = LinearGradient.two_color(
            Color.from_hex("#FF2050"), Color.from_hex("#2060FF")
        )

        def sample_bar(value):
            progress.value = value
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            samples = []
            for logical_x in (58, 150, 267):
                offset = 4 * (round(193 * window.scale) * width + round(logical_x * window.scale))
                samples.append(tuple(rgba[offset:offset + 3]))
            return samples

        track = sample_bar(0)
        half = sample_bar(50)
        full = sample_bar(100)
        assert half[:2] == full[:2] and half[2] == track[2] != full[2]
        assert half[0][0] > half[0][2] and full[2][2] > full[2][0]
        assert len(set(full)) == 3 and sample_bar(50) == half
        assert renderer._contexts[hwnd] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_ring_sweep_reveals_fixed_gpu_colors_and_restores_theme_accent():
    renderer = WgpuRenderer()
    app = App(platform_backend=_isolated_backend(), renderer=renderer)
    window = app.add_window(Window(width=320, height=220))
    scale = LinearGradient(Point(0, .5), Point(1, .5), (
        GradientStop(0, Color.from_hex("#B558EF")), GradientStop(.5, Color.from_hex("#35ACF1")),
        GradientStop(1, Color.from_hex("#00D99C")),
    ))
    ring = ProgressRing(bounds=Rect(60, 20, 160, 160), theme=FUTURE_DARK, thickness=20,
                        segments=64, sweep_stops=scale.stops)
    mount(window, ring)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        offsets = [(index + .5) / 64 for index in (4, 21, 40, 58)]

        def sample(value):
            ring.value = value
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            pixels = []
            for offset in offsets:
                angle = math.tau * offset
                x = round((140 + 70 * math.sin(angle)) * window.scale)
                y = round((100 - 70 * math.cos(angle)) * window.scale)
                pos = 4 * (y * width + x)
                pixels.append(tuple(rgba[pos:pos + 3]))
            return pixels

        def rgb(color):
            # The GPU encodes linear surface colors into the sRGB readback.
            def channel(c):
                return round(255 * (12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055))

            return pytest.approx(tuple(channel(c) for c in (color.r, color.g, color.b)), abs=1)

        track = sample(0)
        assert all(color == rgb(FUTURE_DARK.surface_color("border")) for color in track)
        half = sample(42)
        full = sample(100)
        assert half[:2] == full[:2] and half[2:] == track[2:]
        for pixel, offset in zip(full, offsets, strict=True):
            assert pixel == rgb(scale.color_at(offset))
        assert sample(42) == half
        ring.sweep_stops = (GradientStop(0, scale.stops[-1].color),
                            GradientStop(1, scale.stops[-1].color))
        recolored = sample(42)
        assert all(color == rgb(scale.stops[-1].color) for color in recolored[:2])
        assert recolored[2:] == track[2:]
        ring.enabled = False
        assert all(color == rgb(FUTURE_DARK.surface_color("disabled")) for color in sample(100))
        ring.enabled = True
        ring.sweep_stops = None
        assert all(color == rgb(FUTURE_DARK.surface_color("accent")) for color in sample(100))
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_arrow_keys_paint_the_short_last_step_and_restore_the_previous_thumb() -> None:
    app = App(platform_backend=_isolated_backend(), renderer=WgpuRenderer())
    window = app.add_window(Window(width=360, height=200))
    single = Slider(bounds=Rect(20, 24, 218, 40), maximum=10, step=3, value=9)
    interval = RangeSlider(bounds=Rect(20, 84, 218, 40), maximum=10, step=3,
                           lower_value=3, upper_value=9)
    root = Component()
    root.add(single, interval)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        hwnd = window.native_handle.value
        context = app.renderer._contexts[hwnd]
        user32 = _user32()

        def press(key):
            user32.SendMessageW(hwnd, 0x0100, key, 1)
            user32.SendMessageW(hwnd, 0x0101, key, 1)
            app.process_events()

        def end_pixel(y):
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            offset = 4 * (round(y * window.scale) * width + round(229 * window.scale))
            return rgba[offset:offset + 3]

        for slider, y in ((single, 44), (interval, 104)):
            press(0x09)
            if slider is interval:
                press(0x09)
                assert interval.active_thumb == "upper"
            assert window.focused_component is slider
            before = end_pixel(y)
            press(0x27)
            assert (single.value if slider is single else interval.upper_value) == 10
            assert end_pixel(y) != before
            press(0x25)
            assert (single.value if slider is single else interval.upper_value) == 9
            assert end_pixel(y) == before
        assert app.renderer._contexts[hwnd] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_slider_color_scale_stays_in_place_as_either_handle_moves() -> None:
    renderer = WgpuRenderer()
    app = App(platform_backend=_isolated_backend(), renderer=renderer)
    window = app.add_window(Window(width=360, height=180))
    scale = LinearGradient.two_color(Color.from_hex("#FF3050"), Color.from_hex("#2050FF"))
    single = Slider(bounds=Rect(20, 25, 218, 40), value=100, fill_gradient=scale)
    interval = RangeSlider(bounds=Rect(20, 85, 218, 40), lower_value=0, upper_value=100,
                           fill_gradient=scale)
    root = Component()
    root.add(single, interval)
    mount(window, root)
    try:
        app.start()
        context = renderer._contexts[window.native_handle.value]

        def samples():
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            rows = []
            for y in (45, 105):
                row = round(y * window.scale) * width
                offsets = [4 * (row + round(x * window.scale)) for x in (69, 129, 189)]
                rows.append(tuple(bytes(rgba[i:i + 3]) for i in offsets))
            return rows

        full, both = samples()
        assert full == both and len(set(full)) == 3
        assert full[0][0] > full[0][2] and full[2][2] > full[2][0]
        single.value = 0
        interval.lower_value = 100
        empty, collapsed = samples()
        assert empty == collapsed and len(set(empty)) == 1
        single.value = 65
        interval.lower_value = 35
        interval.upper_value = 65
        prefix, middle = samples()
        assert prefix == (full[0], full[1], empty[2])
        assert middle == (empty[0], full[1], empty[2])
        interval.upper_value = 100
        assert samples()[1] == (empty[0], full[1], full[2])
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_fractional_ring_leaves_visible_space_until_completion() -> None:
    renderer = WgpuRenderer()
    app = App(platform_backend=_isolated_backend(), renderer=renderer)
    window = app.add_window(Window(width=320, height=220))
    ring = ProgressRing(bounds=Rect(40, 20, 200, 180), segments=8, thickness=16)
    mount(window, ring)
    try:
        app.start()
        context = renderer._contexts[window.native_handle.value]

        def top_edge(value):
            ring.value = value
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            row = round(28 * window.scale) * width
            offsets = [4 * (row + round(x * window.scale)) for x in (132, 138, 142, 148)]
            return [bytes(rgba[offset:offset + 3]) for offset in offsets]

        empty, first, last, full = [top_edge(value) for value in (0, 1, 99, 100)]
        assert empty[0] != full[0]
        assert first == [empty[0], empty[1], full[2], empty[3]]
        assert last == [full[0], empty[1], full[2], full[3]]
        assert top_edge(1) == first
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_tooltip_renders_complete_hard_and_soft_lines_on_wgpu():
    renderer = WgpuRenderer(background=Color(0, 0, 0))
    app = App(platform_backend=_isolated_backend(), renderer=renderer)
    window = app.add_window(Window(width=460, height=246))
    root = Component()
    tip = Tooltip("", bounds=Rect(16, 16, 176, 80), initially_open=True, padding=10,
                  font_size=16, background=Color(0, 0, 0), foreground=Color(1, 1, 1))
    reference = Label("", bounds=Rect(0, 0, 1, 1), font_size=16, color=Color(1, 1, 1))
    root.add(tip, reference)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        phrase = "Focus the field to edit its name."
        for hint, box_width, multiple in (("Save\r\nZapisz zmiany", 176, True),
                                          (phrase, 176, True), (phrase, 380, False),
                                          ("Save", 176, False)):
            top = 10 if multiple else 30
            height = 60 if multiple else 20
            tip.bounds = Rect(16, 16, box_width, 80)
            tip.text = reference.text = hint
            reference.bounds = Rect(26, 128 + top, box_width - 20, height)
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, pixels = context.read_scene_rgba()
            stride = width * 4
            y = round(16 * window.scale)
            ref_y = round(128 * window.scale)
            length = round(80 * window.scale) * stride
            actual = bytes(pixels[y * stride:y * stride + length])
            assert actual == bytes(pixels[ref_y * stride:ref_y * stride + length])
            assert max(actual[::4]) > 220
            if multiple:
                # Read the glyphs below the first 20-DIP line, including Polish accents.
                lower = actual[round(30 * window.scale) * stride:]
                assert max(lower[::4]) > 220
        assert renderer._contexts[window.native_handle.value] is context
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="retained widget smoke requires Windows")
def test_escape_removes_hover_hint_pixels_and_preserves_focused_selection():
    renderer = WgpuRenderer()
    app = App(platform_backend=_isolated_backend(), renderer=renderer)
    window = app.add_window(Window(width=400, height=240))
    field = Input("Atlas workbench", bounds=Rect(16, 16, 260, 44))
    chip = Chip("Keyboard help", bounds=Rect(16, 80, 150, 36))
    tip = Tooltip("Edit the name.\nTab moves to the next field.", target=chip,
                  bounds=Rect(16, 132, 300, 58), background=Color(0, 1, 0))
    mount(window, Component().add(field, chip, tip))
    try:
        app.start()
        app.process_events()
        hwnd = window.native_handle.value
        context = renderer._contexts[hwnd]
        user32 = _user32()
        window.focus_component(field)
        field.select(6, 15)
        point = _lparam(round(55 * window.scale), round(96 * window.scale))

        def send(message, key=0, data=0):
            user32.SendMessageW(hwnd, message, key, data)
            _dispatch_sent_messages(app)

        def frame():
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, pixels = context.read_scene_rgba()
            pos = 4 * (round(140 * window.scale) * width + round(60 * window.scale))
            field_end = 4 * round(60 * window.scale) * width
            return tuple(pixels[pos:pos + 3]), bytes(pixels[:field_end])

        send(0x0200, data=point)
        color, selection = frame()
        assert color == (0, 255, 0) and tip.is_open
        send(0x0100, 0x1B, 1)
        send(0x0102, 0x1B, 1)
        send(0x0101, 0x1B, 0xC0000001)
        send(0x0200, data=point)
        after, field_pixels = frame()
        assert after != color and not tip.is_open and field_pixels == selection
        assert window.focused_component is field and field.selected_text == "workbench"
        send(0x02A3)
        send(0x0200, data=point)
        assert tip.is_open and frame() == (color, selection)
        assert renderer._contexts[hwnd] is context
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
