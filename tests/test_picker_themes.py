from dataclasses import replace
from datetime import date, time

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Button,
    Calendar,
    ColorPicker,
    Component,
    DatePicker,
    TimePicker,
    Window,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Color, Rect, SceneNodeKind

KINDS = (Calendar, DatePicker, TimePicker, ColorPicker)


def make_control(kind, **kwargs):
    values = {
        Calendar: {"selected_date": date(2026, 10, 16), "min_date": date(2026, 10, 10)},
        DatePicker: {"value": date(2026, 10, 16)},
        TimePicker: {"value": time(10, 30), "show_seconds": True},
        ColorPicker: {"value": Color.from_hex("#336699CC")},
    }
    return kind(bounds=Rect(10, 10, 420, 330), **values[kind], **kwargs)


def style(control):
    return [(n.key, n.fill, n.font_family, n.corner_radius)
            for n in control.build_scene_node().walk()]


@pytest.mark.parametrize("kind", KINDS)
def test_picker_theme_inheritance_scope_reset_and_font_override(kind):
    control = make_control(kind)
    original = style(control)
    root = Component(theme=FUTURE_DARK).add(control)
    root.theme = replace(FUTURE_LIGHT, font_family="Arial", control_radius=16)
    scene = control.build_scene_node()
    assert scene.fill == FUTURE_LIGHT.surface_color("surface")
    assert scene.corner_radius.top_left == 16
    assert all(n.font_family == "Arial" for n in scene.walk() if n.kind is SceneNodeKind.TEXT)
    control.theme = FUTURE_DARK
    pinned = style(control)
    root.theme = None
    assert style(control) == pinned
    control.theme = None
    assert style(control) == original
    overridden = make_control(kind, theme=FUTURE_DARK, font_family="Consolas")
    overridden.theme = FUTURE_LIGHT
    assert all(n.font_family == "Consolas" for n in overridden.build_scene_node().walk()
               if n.kind is SceneNodeKind.TEXT)


@pytest.mark.parametrize("kind", KINDS)
def test_picker_theme_change_keeps_values_active_segment_and_focus(kind):
    control = make_control(kind)
    root = Component(theme=FUTURE_DARK).add(control)
    window = Window(width=600, height=450)
    runtime = mount(window, root)
    changed = []
    for event in ("date_changed", "time_changed", "color_changed", "month_changed"):
        control.on(event, changed.append)
    try:
        window.focus_component(control)
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x27)
        )
        before = control.accessibility_snapshot(focused=control)
        changed.clear()
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            assert control.accessibility_snapshot(focused=control) == before
            assert not changed and window.focused_component is control
            frames = [n for n in control.build_scene_node().walk() if ":theme-focus:" in n.key]
            assert len(frames) == 4
            assert all(n.fill == theme.surface_color("focus") for n in frames)
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", KINDS)
def test_picker_navigation_respects_child_focus_and_cancelled_defaults(kind):
    control = make_control(kind, theme=FUTURE_DARK)
    child = Button("Child", bounds=Rect(10, 360, 100, 40))
    control.add(child)
    root = Component().add(control)
    window = Window(width=600, height=450)
    runtime = mount(window, root)
    try:
        before = control.accessibility_snapshot()
        window.focus_component(child)
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x27)
        )
        assert control.accessibility_snapshot() == before
        window.focus_component(control)
        root.on("key_down", lambda e: e.prevent_default(), capture=True)
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x27)
        )
        assert control.accessibility_snapshot() == before
    finally:
        runtime.unmount()


def test_color_picker_srgb_conversion_preserves_public_color_and_alpha():
    control = make_control(ColorPicker, theme=FUTURE_LIGHT)
    nodes = {n.key: n for n in control.build_scene_node().walk()}
    preview = nodes[control.key + ":preview"]
    assert control.hex_value == "#336699CC"
    assert control.value == Color.from_hex("#336699CC")
    assert preview.fill.r == pytest.approx(0.03310477)
    assert preview.fill.g == pytest.approx(0.13286832)
    assert preview.fill.b == pytest.approx(0.31854678)
    assert preview.fill.a == pytest.approx(0.8)
    assert any(":checker:preview:" in key for key in nodes)
    assert any(":checker:alpha:" in key for key in nodes)
    assert all(n.kind is SceneNodeKind.PATH for key, n in nodes.items() if ":track:" in key)
    assert len(nodes) < 800  # Bounded strips and checkerboards, independent of DPI.
    assert nodes[control.key + ":thumb:hue"].fill == Color(1, 1, 1)
    assert nodes[control.key + ":thumb-outline:hue"].fill == Color(0, 0, 0)


def test_color_picker_drag_survives_theme_change_outside_widget_and_ends_on_release():
    control = make_control(ColorPicker, theme=FUTURE_DARK)
    root = Component().add(control)
    window = Window(width=800, height=450)
    runtime = mount(window, root)
    track = control.track_bounds("saturation")

    def send(kind, x):
        window._apply_platform_event(PlatformEvent(
            kind, NativeWindowHandle(1), x=x, y=track.y + 5, button=PointerButton.LEFT
        ))

    try:
        send(PlatformEventKind.POINTER_DOWN, track.x + 20)
        assert window.pointer_capture_component is control
        control.theme = FUTURE_LIGHT
        send(PlatformEventKind.POINTER_MOVE, 700)
        assert control.channel_value("saturation") == 1
        send(PlatformEventKind.POINTER_UP, 700)
        assert window.pointer_capture_component is None and control._drag_channel is None
        send(PlatformEventKind.POINTER_DOWN, track.x + 20)
        window.release_pointer_capture()
        assert control._drag_channel is None
    finally:
        runtime.unmount()
