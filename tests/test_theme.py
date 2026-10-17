from dataclasses import FrozenInstanceError, replace

import pytest

from swirui import ButtonVariant, Palette, Theme, Window
from swirui.rendering import Color, Rect, SceneNodeKind
from swirui.widgets import Button, Card, Checkbox, Input, Label, Slider, Switch, mount

BOUNDS = Rect(0, 0, 240, 44)


def test_theme_converts_srgb_surfaces_without_changing_text_or_alpha() -> None:
    theme = Theme(palette=Palette(accent="#80808080"))
    assert theme.surface_color("accent").r == pytest.approx(0.2158605)
    assert theme.text_color("accent").r == pytest.approx(128 / 255)
    assert theme.surface_color("accent").a == pytest.approx(128 / 255)


def test_themes_are_immutable_and_independent() -> None:
    first = Theme()
    second = replace(first, palette=replace(first.palette, accent="#55DDCC"))
    assert first.palette.accent != second.palette.accent
    with pytest.raises(FrozenInstanceError):
        first.control_radius = 99  # type: ignore[misc]
    one = Button("One", bounds=BOUNDS, theme=first)
    two = Button("Two", bounds=BOUNDS, theme=second)
    assert one.build_scene_node().fill != two.build_scene_node().fill


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_theme_geometry_is_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        Theme(control_radius=value)


def test_explicit_widget_colors_and_geometry_override_theme() -> None:
    custom = Color(0.4, 0.2, 0.1)
    node = Button(
        "Custom",
        bounds=BOUNDS,
        theme=Theme(),
        background=custom,
        corner_radius=3,
        font_family="Arial",
    ).build_scene_node()
    assert node.fill == custom
    assert node.corner_radius.top_left == 3
    assert node.children[0].font_family == "Arial"


def test_button_variants_and_disabled_text_have_distinct_semantics() -> None:
    theme = Theme()
    primary = Button("Primary", bounds=BOUNDS, theme=theme)
    secondary = Button("Secondary", bounds=BOUNDS, theme=theme, variant=ButtonVariant.SECONDARY)
    ghost = Button("Ghost", bounds=BOUNDS, theme=theme, variant=ButtonVariant.GHOST)
    assert primary.build_scene_node().fill == theme.surface_color("accent")
    assert secondary.build_scene_node().fill == theme.surface_color("raised")
    assert ghost.build_scene_node().fill == Color(0, 0, 0, 0)
    primary.enabled = False
    disabled = primary.build_scene_node()
    assert disabled.fill == theme.surface_color("disabled")
    assert disabled.children[0].fill == theme.text_color("disabled_text")


@pytest.mark.parametrize("factory", [Button, Input])
def test_keyboard_focus_has_visible_theme_ring(factory: type[Button] | type[Input]) -> None:
    theme = Theme()
    widget = factory("Focus", bounds=BOUNDS, theme=theme)
    window = Window()
    runtime = mount(window, widget)
    window.focus_component(widget)
    node = widget.build_scene_node()
    assert node.fill == theme.surface_color("focus")
    assert any(child.key.endswith(":focus-surface") for child in node.children)
    runtime.unmount()


def test_theme_reaches_input_toggle_slider_surface_and_text() -> None:
    theme = Theme(palette=Palette(accent="#55DDCC", surface="#202030", text="#FFF4DE"))
    assert Input(bounds=BOUNDS, theme=theme).build_scene_node().fill == theme.surface_color(
        "raised"
    )
    checkbox = Checkbox("Check", bounds=BOUNDS, checked=True, theme=theme).build_scene_node()
    assert next(n for n in checkbox.walk() if n.key.endswith(":indicator")).fill == (
        theme.surface_color("accent")
    )
    switch = Switch("Toggle", bounds=BOUNDS, checked=True, theme=theme).build_scene_node()
    assert next(n for n in switch.walk() if n.key.endswith(":track")).fill == (
        theme.surface_color("accent")
    )
    slider = Slider(bounds=BOUNDS, value=50, theme=theme).build_scene_node()
    assert any(n.fill == theme.surface_color("accent") for n in slider.walk())
    card = Card(bounds=BOUNDS, theme=theme, show_shadow=False).build_scene_node()
    assert any(n.fill == theme.surface_color("surface") for n in card.walk())
    label = Label("Text", bounds=BOUNDS, theme=theme).build_scene_node()
    assert label.kind is SceneNodeKind.TEXT
    assert label.fill == theme.text_color("text")
