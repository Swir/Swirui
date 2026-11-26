"""Actual GPU pixels across the expanded core-control theme scope."""

import ctypes
import math
import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Badge,
    Checkbox,
    Chip,
    Expander,
    Panel,
    ProgressBar,
    ProgressRing,
    RadioButton,
    SplitView,
    Switch,
    Toast,
    Tooltip,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_tab_focus_remains_visible_on_checked_controls_with_matching_accent(record_property):
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=360, height=240))
    theme = FUTURE_DARK.with_accent("#7FE0BF")
    assert theme.palette.accent == theme.palette.focus
    root = Panel(bounds=Rect(0, 0, 360, 240), theme=theme)
    controls = [cls("Motion", checked=True, bounds=Rect(40, 24 + i * 60, 180, 22))
                for i, cls in enumerate((Checkbox, RadioButton, Switch))]
    root.add(*controls)
    mount(window, root)
    try:
        app.start()
        app.process_events()
        hwnd = window.native_handle.value
        context = renderer._contexts[hwnd]
        send = app.platform_backend._user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t

        def frame():
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            return context.read_scene_rgba()

        def pixel(capture, x, y):
            width, _, rgba = capture
            offset = (int(y * window.scale) * width + int(x * window.scale)) * 4
            return tuple(rgba[offset:offset + 3])

        def color(role):
            c = theme.text_color(role)
            return tuple(round(v * 255) for v in (c.r, c.g, c.b))

        idle = frame()
        for control in controls:
            x = control.bounds.x + control.indicator_width / 2
            y = control.bounds.y
            assert pixel(idle, x, y + 2.5) == pytest.approx(color("accent"), abs=1)
            send(hwnd, 0x0100, 0x09, 1)  # Tab down and up on this window.
            send(hwnd, 0x0101, 0x09, 0xC0000001)
            app.process_events()
            assert window.focused_component is control and control.checked
            focused = frame()
            assert pixel(focused, x, y + 1.5) == pytest.approx(color("focus"), abs=1)
            # The one-DIP separator is antialiased against the accent on both sides.
            gap = pixel(focused, x, y + 2.5)
            assert math.dist(gap, color("canvas")) < math.dist(gap, color("accent"))
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_core_controls_present_theme_pixels_without_context_or_state_replacement():
    root = Panel(bounds=Rect(0, 0, 620, 420), theme=FUTURE_DARK)
    bar = ProgressBar(bounds=Rect(20, 20, 200, 12), value=40)
    ring = ProgressRing(bounds=Rect(20, 330, 70, 70), value=40)
    chip = Chip("Selected", bounds=Rect(20, 60, 140, 42), selected=True)
    badge = Badge("Badge", bounds=Rect(180, 60, 140, 42))
    tip = Tooltip("Tooltip", bounds=Rect(340, 60, 200, 42), initially_open=True)
    expander = Expander("Details", bounds=Rect(20, 130, 260, 44), expanded=True)
    toast = Toast("Message", bounds=Rect(320, 140, 260, 100), kind="warning")
    split = SplitView(bounds=Rect(20, 220, 260, 90), split_ratio=0.4)
    controls = [bar, ring, chip, badge, tip, expander, toast, split]
    root.add(*controls)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=620, height=420))
    mount(window, root)
    try:
        app.start()
        assert window.native_handle is not None
        context = renderer._contexts[window.native_handle.value]
        for theme in (FUTURE_DARK, FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, _height, pixels = context.read_scene_rgba()
            for x, y, role in (
                (40, 26, "accent"),
                (180, 26, "border"),
                (90, 63, "accent"),
                (250, 63, "raised"),
                (440, 63, "raised"),
                (150, 133, "raised"),
                (500, 232, "raised"),
                (324, 190, "warning"),
                (124, 240, "border"),
                (56, 333, "accent"),
            ):
                color = theme.text_color(role)
                expected = (round(color.r * 255), round(color.g * 255), round(color.b * 255), 255)
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                assert tuple(pixels[offset : offset + 4]) == pytest.approx(expected, abs=1), (
                    x,
                    y,
                    role,
                )
            assert renderer._contexts[window.native_handle.value] is context
            assert root.children == controls
            assert bar.value == ring.value == 40
            assert chip.selected and expander.expanded and tip.is_open
            assert split.split_ratio == 0.4
    finally:
        app.stop()
