from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Button,
    Component,
    DockPane,
    DockWorkspace,
    Inspector,
    PropertyGrid,
    PropertyItem,
    Terminal,
    Window,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Color, Rect, SceneNodeKind

KINDS = (PropertyGrid, Inspector, DockWorkspace, Terminal)


def make_control(kind, **kwargs):
    if kind in (PropertyGrid, Inspector):
        return kind([PropertyItem("title", "Title", "Draft"), PropertyItem("size", "Size", 12)],
                    bounds=Rect(0, 0, 500, 280), **kwargs)
    if kind is DockWorkspace:
        return kind([DockPane(i, f"Pane {i}", Component()) for i in range(3)],
                    bounds=Rect(0, 0, 500, 280), **kwargs)
    control = kind(bounds=Rect(0, 0, 500, 280), **kwargs)
    control.writeln("plain \x1b[31mred\x1b[0m plain")
    return control


def style(control):
    return [(n.key, n.fill, n.font_family, n.corner_radius)
            for n in control.build_scene_node().walk()]


@pytest.mark.parametrize("kind", KINDS)
def test_application_theme_inheritance_scope_and_legacy_reset(kind):
    control = make_control(kind)
    original = style(control)
    root = Component(theme=FUTURE_DARK).add(control)
    root.theme = replace(FUTURE_LIGHT, font_family="Arial", monospace_family="Consolas")
    nodes = list(control.build_scene_node().walk())
    assert all(n.font_family == ("Consolas" if kind is Terminal else "Arial")
               for n in nodes if n.kind is SceneNodeKind.TEXT)
    control.theme = FUTURE_DARK
    pinned = style(control)
    root.theme = None
    assert style(control) == pinned
    control.theme = None
    assert style(control) == original


@pytest.mark.parametrize("kind", KINDS)
def test_application_theme_preserves_state_focus_and_explicit_font(kind):
    control = make_control(kind, theme=FUTURE_DARK, font_family="Arial")
    if kind in (PropertyGrid, Inspector):
        control.begin_edit("title").set_edit_buffer("Unsaved")
    elif kind is DockWorkspace:
        control.activate_pane(2)
    else:
        control.submit("old")
        control.input_text = "draft"
    window = Window(width=600, height=400)
    runtime = mount(window, control)
    try:
        window.focus_component(control)
        state = control.accessible_value_text
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            control.theme = theme
            assert window.focused_component is control and control.accessible_value_text == state
            nodes = list(control.build_scene_node().walk())
            assert len([n for n in nodes if ":theme-focus:" in n.key]) == 4
            assert all(n.font_family == "Arial" for n in nodes if n.kind is SceneNodeKind.TEXT)
        if kind in (PropertyGrid, Inspector):
            assert control.edit_buffer == "Unsaved"
            control.commit_edit()
            assert control.items[0].value == "Unsaved"
        elif kind is DockWorkspace:
            assert control.active_key == 2 and control.panes[2].content.visible
        else:
            assert control.input_text == "draft" and control.history == ("old",)
    finally:
        runtime.unmount()


def test_terminal_recolors_old_output_without_rewriting_history_or_pending_ansi():
    control = make_control(Terminal, theme=FUTURE_DARK)
    control.write("\x1b[3")
    stored = control._lines
    control.theme = FUTURE_LIGHT
    assert control._lines is stored
    control.write("2mgreen\x1b[39mnormal")
    nodes = [n for n in control.build_scene_node().walk() if ":line:" in n.key]
    assert nodes[0].fill == FUTURE_LIGHT.text_color("text")
    assert next(n for n in nodes if n.text == "red").fill == Color.from_hex("#A9273D")
    assert next(n for n in nodes if n.text == "green").fill == Color.from_hex("#146F52")
    assert nodes[-1].fill == FUTURE_LIGHT.text_color("text")
    lines = control.lines
    control.theme = FUTURE_DARK
    assert control.lines == lines and control._lines is stored


def test_terminal_explicit_colors_override_runtime_palette():
    custom = Color(1, 0, 0)
    colors = {31: custom}
    control = make_control(Terminal, theme=FUTURE_DARK, foreground=custom,
                           background=custom, ansi_colors=colors, corner_radius=3)
    colors[31] = Color(0, 1, 0)
    control.theme = FUTURE_LIGHT
    node = control.build_scene_node()
    assert node.fill == custom and node.corner_radius.top_left == 3
    assert all(n.fill == custom for n in node.walk() if ":line:" in n.key)


@pytest.mark.parametrize("kind", KINDS)
def test_application_keyboard_does_not_edit_ancestors_or_cancelled_events(kind):
    control = make_control(kind, theme=FUTURE_DARK)
    child = Button("Child", bounds=Rect(0, 300, 100, 40))
    control.add(child)
    root = Component().add(control)
    window = Window(width=600, height=400)
    runtime = mount(window, root)
    try:
        state = control.accessible_value_text
        window.focus_component(child)
        window._apply_platform_event(PlatformEvent(
            PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x27
        ))
        assert control.accessible_value_text == state
        window.focus_component(control)
        root.on("key_down", lambda e: e.prevent_default(), capture=True)
        window._apply_platform_event(PlatformEvent(
            PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x23
        ))
        assert control.accessible_value_text == state
    finally:
        runtime.unmount()


def test_dock_keyboard_activation_keeps_content_identity_and_theme():
    control = make_control(DockWorkspace, theme=FUTURE_LIGHT)
    contents = tuple(p.content for p in control.panes)
    window = Window(width=600, height=400)
    runtime = mount(window, control)
    try:
        window.focus_component(control)
        for key, expected in ((0x23, 2), (0x27, 0), (0x25, 2), (0x24, 0)):
            window._apply_platform_event(PlatformEvent(
                PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=key
            ))
            assert control.active_center_key == expected
            assert tuple(p.content for p in control.panes) == contents
            assert contents[expected].visible and contents[expected].effective_theme == FUTURE_LIGHT
    finally:
        runtime.unmount()
