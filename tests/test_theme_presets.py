from dataclasses import fields

import pytest

from swirui import THEME_PRESETS, Button, Input, Panel, ThemePackage, Window, mount
from swirui.rendering import Rect


def luminance(theme, role):
    color = theme.surface_color(role)
    return 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b


def contrast(theme, foreground, background):
    a, b = luminance(theme, foreground), luminance(theme, background)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


@pytest.mark.parametrize("name,theme", THEME_PRESETS.items())
def test_builtin_palette_readability_for_authored_text_pairs(name, theme):
    for background in ("canvas", "surface", "raised", "hover", "pressed", "selection"):
        assert contrast(theme, "text", background) >= 4.5, (name, "text", background)
    for background in ("canvas", "surface", "raised"):
        assert contrast(theme, "muted", background) >= 4.5, (name, "muted", background)
    for background in ("accent", "accent_hover", "accent_pressed"):
        assert contrast(theme, "on_accent", background) >= 4.5, (name, "on_accent", background)
    assert all(len(getattr(theme.palette, field.name)) == 7 for field in fields(theme.palette))


def test_presets_are_readonly_and_export_complete_theme_package():
    assert set(THEME_PRESETS) == {
        "future_dark", "future_light", "neon_blue", "neon_green", "matrix", "cyberpunk",
        "oled", "minimal", "professional",
    }
    with pytest.raises(TypeError):
        THEME_PRESETS["neon_blue"] = THEME_PRESETS["matrix"]
    package = ThemePackage("Built-in appearances", THEME_PRESETS, "future_dark")
    assert ThemePackage.loads(package.dumps()) == package
    assert THEME_PRESETS["oled"].palette.canvas == "#000000"
    assert THEME_PRESETS["oled"].palette.surface == "#000000"


def test_all_presets_restyle_same_controls_without_losing_edits_or_local_scope():
    root = Panel(bounds=Rect(0, 0, 600, 320))
    field = Input("A draft stays", bounds=Rect(20, 20, 300, 44))
    action = Button("Create", bounds=Rect(20, 100, 160, 44))
    local = Input("Local", bounds=Rect(20, 180, 300, 44), theme=THEME_PRESETS["oled"])
    root.add(field, action, local)
    window = Window()
    runtime = mount(window, root)
    try:
        window.focus_component(field)
        field.select(2, 7)
        for theme in THEME_PRESETS.values():
            root.theme = theme
            assert field.value == "A draft stays" and field.selected_text == "draft"
            assert window.focused_component is field
            assert action.build_scene_node().fill == theme.surface_color("accent")
            assert any(n.text == "A draft stays" and n.font_family == theme.font_family
                       for n in field.build_scene_node().walk())
            assert local.effective_theme is THEME_PRESETS["oled"]
    finally:
        runtime.unmount()
