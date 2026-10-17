from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Button,
    CommandItem,
    CommandPalette,
    Component,
    ContextMenu,
    MenuBar,
    Ribbon,
    RibbonGroup,
    Toolbar,
    Window,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect, SceneNodeKind

KINDS = [Toolbar, MenuBar, Ribbon, ContextMenu, CommandPalette]


def make_control(kind, **kwargs):
    items = [CommandItem(i, f"Action {i}", f"Ctrl+{i}", disabled=i == 1) for i in range(20)]
    values = [RibbonGroup(i, f"Group {i}", items) for i in range(10)] if kind is Ribbon else items
    return kind(values, bounds=Rect(0, 0, 420, 200), **kwargs)


def send(window, **kwargs):
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), **kwargs)
    )


@pytest.mark.parametrize("kind", KINDS)
def test_command_theme_inheritance_local_scope_and_legacy_reset(kind):
    control = make_control(kind)
    original = [
        (n.key, n.fill, n.corner_radius, n.font_family) for n in control.build_scene_node().walk()
    ]
    root = Component(theme=FUTURE_DARK).add(control)
    theme = replace(FUTURE_LIGHT, font_family="Arial", control_radius=7)
    root.theme = theme
    node = control.build_scene_node()
    assert node.fill == theme.surface_color("surface") and node.corner_radius.top_left == 7
    assert all(n.font_family == "Arial" for n in node.walk() if n.kind is SceneNodeKind.TEXT)
    control.theme = FUTURE_DARK
    root.theme = None
    assert control.effective_theme == FUTURE_DARK
    control.theme = None
    assert [
        (n.key, n.fill, n.corner_radius, n.font_family) for n in control.build_scene_node().walk()
    ] == original


@pytest.mark.parametrize("kind", KINDS)
def test_command_focus_state_and_selection_survive_theme_switch(kind):
    control = make_control(kind, theme=FUTURE_DARK)
    window = Window(width=500, height=300)
    runtime = mount(window, control)
    try:
        window.focus_component(control)
        send(window, key_code=0x23)
        state = control.accessible_value_text
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            control.theme = theme
            assert control.accessible_value_text == state and window.focused_component is control
            frames = [n for n in control.build_scene_node().walk() if ":theme-focus:" in n.key]
            assert len(frames) == 4
            assert all(
                n.fill == theme.surface_color("focus") and not n.hit_testable for n in frames
            )
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", [Toolbar, MenuBar, Ribbon])
def test_horizontal_command_navigation_reveals_overflow_and_pointer_invokes_it(kind):
    control = make_control(kind)
    window = Window(width=500, height=300)
    runtime = mount(window, control)
    invoked = []
    control.on("command_invoked", lambda e: invoked.append(e.data["key"]))
    try:
        window.focus_component(control)
        send(window, key_code=0x23)
        if kind is Ribbon:
            assert control.selected_key == 9
            for _ in range(18):
                send(window, key_code=0x28)
            assert control.active_command.key == 19
        else:
            assert control.active_item.key == 19
        scene = control.build_scene_node()
        label = next(n for n in scene.walk() if n.text == "Action 19")
        assert label.bounds.x >= 0 and label.bounds.right <= control.bounds.right
        assert len(list(scene.walk())) < 60
        window._apply_platform_event(
            PlatformEvent(
                PlatformEventKind.POINTER_DOWN,
                NativeWindowHandle(1),
                x=label.bounds.x + 3,
                y=label.bounds.y + 3,
                button=PointerButton.LEFT,
            )
        )
        assert invoked == [19]
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", KINDS)
def test_command_navigation_respects_child_focus_and_prevented_defaults(kind):
    control = make_control(kind)
    child = Button("Child", bounds=Rect(0, 220, 100, 30))
    control.add(child)
    root = Component().add(control)
    window = Window(width=500, height=300)
    runtime = mount(window, root)
    try:
        original = control.accessible_value_text
        window.focus_component(child)
        send(window, key_code=0x23)
        assert control.accessible_value_text == original
        window.focus_component(control)
        root.on("key_down", lambda e: e.prevent_default(), capture=True)
        send(window, key_code=0x23)
        assert control.accessible_value_text == original
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", [CommandPalette, ContextMenu])
@pytest.mark.parametrize("width", [80, 210, 420])
def test_popup_shortcut_column_does_not_overlap_label(kind, width):
    control = kind(
        [CommandItem("a", "A long command title", "Ctrl+Shift+A")], bounds=Rect(0, 0, width, 200)
    )
    nodes = list(control.build_scene_node().walk())
    label = next(n for n in nodes if n.text == "A long command title")
    shortcut = next(n for n in nodes if n.text == "Ctrl+Shift+A")
    assert label.bounds.right <= shortcut.bounds.x
    assert shortcut.bounds.right <= width


def test_palette_filters_keep_active_identity_beyond_first_page_and_skip_disabled_prefix():
    items = [CommandItem(i, f"Action {i}", disabled=i < 12) for i in range(40)]
    palette = CommandPalette(items, bounds=Rect(0, 0, 420, 200), dismiss_on_invoke=False)
    palette.activate_key(39)
    palette.set_query("Action")
    palette.theme = FUTURE_LIGHT
    assert palette.active_item.key == 39
    assert any(n.text == "Action 39" for n in palette.build_scene_node().walk())
    palette.set_items(items[:20])
    assert palette.active_item.key == 12
    assert any(n.text == "Action 12" for n in palette.build_scene_node().walk())
    palette.set_query("missing command")
    assert palette.active_item is None and not palette.filtered_items
    assert any(n.text == "No matching commands" for n in palette.build_scene_node().walk())


@pytest.mark.parametrize("height", [32, 46, 64])
def test_short_toolbar_places_shortcuts_beside_labels_without_overlapping(height):
    toolbar = Toolbar([CommandItem("a", "Action", "Ctrl+A")], bounds=Rect(0, 0, 200, height))
    nodes = list(toolbar.build_scene_node().walk())
    label = next(n.bounds for n in nodes if n.text == "Action")
    shortcut = next(n.bounds for n in nodes if n.text == "Ctrl+A")
    assert label.right <= shortcut.x or label.bottom <= shortcut.y
