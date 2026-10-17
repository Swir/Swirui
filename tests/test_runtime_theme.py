from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Button,
    ButtonVariant,
    Card,
    Checkbox,
    CodeEditor,
    Component,
    Input,
    Label,
    Palette,
    Panel,
    RangeSlider,
    Slider,
    Switch,
    Theme,
    Window,
    mount,
)
from swirui.core import Event
from swirui.rendering import Color, Rect

BOUNDS = Rect(0, 0, 280, 80)
VIOLET = Theme()
OCEAN = Theme(palette=replace(Palette(), accent="#82DEED"), control_radius=20)


def test_theme_inheritance_local_scope_and_reset() -> None:
    root = Component(theme=VIOLET)
    scope = Component(theme=OCEAN)
    inherited = Button("Inherited", bounds=BOUNDS)
    local = Button("Local", bounds=BOUNDS, theme=OCEAN)
    nested = Input("state", bounds=BOUNDS)
    root.add(inherited, local, scope)
    scope.add(nested)
    assert inherited.effective_theme == VIOLET
    assert local.effective_theme == nested.effective_theme == OCEAN
    root.theme = OCEAN
    assert inherited.build_scene_node().fill == OCEAN.surface_color("accent")
    scope.theme = None
    root.theme = VIOLET
    assert nested.effective_theme == VIOLET
    assert local.effective_theme == OCEAN
    local.theme = None
    assert local.effective_theme == VIOLET


def test_reparent_and_detach_resolve_theme_without_stale_subscription() -> None:
    first, second = Component(theme=VIOLET), Component(theme=OCEAN)
    button = Button("Move", bounds=BOUNDS)
    legacy_color = button.build_scene_node().fill
    first.add(button)
    second.add(button)
    assert button.effective_theme == OCEAN
    first.theme = OCEAN
    assert button.parent is second
    second.remove(button)
    assert button.effective_theme is None
    assert button.build_scene_node().fill == legacy_color
    second.theme = VIOLET
    assert button.effective_theme is None


def test_late_added_control_observes_inherited_theme_during_mount() -> None:
    seen = []

    class ObservingButton(Button):
        def on_mount(self, window: Window) -> None:
            seen.append(self.effective_theme)

    root = Component(theme=OCEAN)
    window = Window()
    mount(window, root)
    updates = []
    window.on("scene_changed", updates.append)
    root.add(ObservingButton("New", bounds=BOUNDS))
    assert seen == [OCEAN]
    assert len(updates) == 1


def test_runtime_change_preserves_identity_text_selection_focus_and_undo() -> None:
    root = Panel(bounds=Rect(0, 0, 600, 300), theme=VIOLET)
    editor = CodeEditor("first", bounds=BOUNDS)
    field = Input("untouched", bounds=Rect(0, 100, 280, 80))
    toggle = Switch("Enabled", checked=True, bounds=Rect(300, 0, 200, 50))
    root.add(editor, field, toggle)
    window = Window(width=600, height=300)
    mount(window, root)
    window.focus_component(editor)
    editor.select_all()
    editor._replace_selection("changed", input_event=Event("test", editor))
    editor.select_all()
    scene_updates = []
    window.on("scene_changed", scene_updates.append)
    children = tuple(root.children)
    root.theme = OCEAN
    assert tuple(root.children) == children
    assert window.focused_component is editor
    assert editor.value == editor.selected_text == "changed"
    assert field.value == "untouched" and toggle.checked
    editor.undo()
    assert editor.value == "first"
    # One atomic theme transaction, plus the explicit undo after it.
    assert len(scene_updates) == 2


def test_explicit_style_overrides_survive_inherited_theme_changes() -> None:
    red = Color(1, 0, 0)
    root = Component(theme=VIOLET)
    button = Button("Fixed", bounds=BOUNDS, background=red, corner_radius=3, font_family="Arial")
    label = Label("Text", bounds=BOUNDS)
    panel = Panel(bounds=BOUNDS)
    root.add(button, label, panel)
    label.color = red
    label.font_family = "Arial"
    panel.background = red
    root.theme = OCEAN
    assert button.build_scene_node().fill == red
    assert button._corner_radius == 3 and button._font_family == "Arial"
    assert label.color == red and label.font_family == "Arial"
    assert panel.background == red


def test_core_controls_follow_theme_without_changing_values() -> None:
    root = Component(theme=VIOLET)
    controls = [
        Card(bounds=BOUNDS),
        Label("label", bounds=BOUNDS),
        Checkbox("check", bounds=BOUNDS, checked=True),
        Slider(bounds=BOUNDS, value=23),
        RangeSlider(bounds=BOUNDS, lower_value=15, upper_value=65),
    ]
    root.add(*controls)
    root.theme = OCEAN
    assert all(control.effective_theme == OCEAN for control in controls)
    assert controls[0].background == OCEAN.surface_color("surface")
    assert controls[1].color == OCEAN.text_color("text")
    assert controls[2].checked
    assert controls[3].value == 23 and controls[3]._accent == OCEAN.surface_color("accent")
    assert (controls[4].lower_value, controls[4].upper_value) == (15, 65)


def test_variant_switch_and_standalone_fallback_allow_inheritance() -> None:
    button = Button("Action", bounds=BOUNDS, variant=ButtonVariant.PRIMARY)
    root = Component(theme=OCEAN)
    root.add(button)
    assert button.theme is None and button.effective_theme == OCEAN
    button.variant = ButtonVariant.GHOST
    assert button.build_scene_node().fill.a == 0
    button.variant = ButtonVariant.SECONDARY
    assert button.build_scene_node().fill == OCEAN.surface_color("raised")
    root.remove(button)
    assert button.effective_theme == VIOLET


def test_theme_observers_see_resolved_descendants_and_equal_assignment_is_quiet() -> None:
    root = Component(theme=VIOLET)
    child = Input(bounds=BOUNDS)
    root.add(child)
    observations = []
    root.on("theme_changed", lambda _: observations.append(child.effective_theme))
    root.theme = OCEAN
    root.theme = replace(OCEAN)
    assert observations == [OCEAN]
    with pytest.raises(TypeError):
        root.theme = "invalid"
    assert root.theme == OCEAN


@pytest.mark.parametrize("theme", [FUTURE_DARK, FUTURE_LIGHT])
def test_presets_keep_readable_text_and_visible_focus(theme: Theme) -> None:
    def luminance(role: str) -> float:
        color = theme.surface_color(role)
        return 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b

    def contrast(first: str, second: str) -> float:
        a, b = sorted((luminance(first), luminance(second)))
        return (b + 0.05) / (a + 0.05)

    for surface in ("canvas", "surface", "raised"):
        assert contrast("text", surface) >= 4.5
        assert contrast("muted", surface) >= 4.5
        assert contrast("focus", surface) >= 3
    assert contrast("on_accent", "accent") >= 4.5
