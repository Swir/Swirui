"""Actual GPU pixels across the expanded core-control theme scope."""

import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Badge,
    Chip,
    Expander,
    Panel,
    ProgressBar,
    ProgressRing,
    SplitView,
    Toast,
    Tooltip,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


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
