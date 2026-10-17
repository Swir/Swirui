from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Autocomplete,
    CodeEditor,
    Component,
    Theme,
    Window,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Color, Rect, SceneNodeKind


def make_control(kind, **kwargs):
    if kind is CodeEditor:
        return kind(
            'if True:\n    return "hello" # note\n',
            bounds=Rect(0, 0, 500, 180), language="python", show_minimap=True, **kwargs,
        )
    control = kind("s", bounds=Rect(0, 0, 320, 44), items=["Swir", "Studio"], **kwargs)
    control.open_suggestions()
    control.emit(
        "key_down",
        event=PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x28),
    )
    return control


def scene_style(control):
    return [
        (n.key, n.fill, n.font_family, n.corner_radius, n.text_spans)
        for n in control.build_scene_node().walk()
    ]


@pytest.mark.parametrize("kind", [CodeEditor, Autocomplete])
def test_advanced_input_theme_scopes_detach_and_legacy_restore(kind):
    control = make_control(kind)
    original = scene_style(control)
    root = Component(theme=FUTURE_DARK).add(control)
    assert scene_style(control) != original
    root.theme = replace(FUTURE_LIGHT, font_family="Arial", monospace_family="Consolas")
    nodes = list(control.build_scene_node().walk())
    expected_font = "Consolas" if kind is CodeEditor else "Arial"
    assert all(n.font_family == expected_font for n in nodes if n.kind is SceneNodeKind.TEXT)
    if kind is CodeEditor:
        gutter = next(n for n in nodes if n.key.endswith(":gutter"))
        assert gutter.fill == FUTURE_LIGHT.surface_color("canvas")
        assert control._syntax_colors["keyword"] == FUTURE_LIGHT.text_color("accent")
        assert control._syntax_colors["comment"] == FUTURE_LIGHT.text_color("muted")
    else:
        surface = next(n for n in nodes if n.key.endswith(":suggestions:surface"))
        assert surface.fill == FUTURE_LIGHT.surface_color("surface")
        assert surface.corner_radius.top_left == FUTURE_LIGHT.control_radius - 1
        selected = next(n for n in nodes if n.key.endswith(":suggestion:0:selected"))
        assert selected.fill == FUTURE_LIGHT.surface_color("selection")
    control.theme = FUTURE_DARK
    pinned = scene_style(control)
    root.theme = FUTURE_LIGHT
    assert scene_style(control) == pinned
    control.theme = None
    root.remove(control)
    assert scene_style(control) == original


def test_code_theme_preserves_partial_explicit_palette_and_undo_state():
    custom = Color(1, 0, 0)
    colors = {"keyword": custom}
    control = make_control(
        CodeEditor, theme=FUTURE_DARK, syntax_colors=colors,
        gutter_background=custom, minimap_foreground=custom,
        foreground=custom, font_family="Arial", current_line_background=custom,
    )
    # Caller mutation must not change the editor's authored overrides.
    colors["keyword"] = Color(0, 1, 0)
    root = Component().add(control)
    window = Window(width=600, height=300)
    runtime = mount(window, root)
    try:
        window.focus_component(control)
        control.select(0, 0)
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.TEXT_INPUT, NativeWindowHandle(1), text="# start\n")
        )
        changed = control.value
        control.select(2, 6)
        state = (control.selected_text, control._caret, control._scroll_offset)
        syntax_cache = control._syntax_lines()
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            control.theme = theme
            assert control.value == changed
            assert (control.selected_text, control._caret, control._scroll_offset) == state
            assert window.focused_component is control
            assert control._syntax_colors["keyword"] == custom
            assert control._syntax_colors["string"] == theme.text_color("success")
            assert control._gutter_background == control._minimap_foreground == custom
            assert control._foreground == control._current_line_background == custom
            assert control._font_family == "Arial"
            assert control._syntax_lines() is syntax_cache
        window._apply_platform_event(
            PlatformEvent(
                PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x5A, ctrl=True
            )
        )
        assert not control.value.startswith("# start")
    finally:
        runtime.unmount()


def test_popup_theme_preserves_query_selection_provider_and_explicit_colors():
    calls = []

    def provide(query, limit):
        calls.append((query, limit))
        return ["Silver", "Sky"]

    custom = Color(0, 1, 0)
    control = make_control(
        Autocomplete, provider=provide, theme=FUTURE_DARK, popup_selected=custom,
        popup_selected_foreground=custom, popup_border=custom,
        background=custom, font_family="Arial",
    )
    control.select(0, 1)
    state = (control.suggestions, control.selected_suggestion, control.selected_text)
    calls_before = list(calls)
    for theme in (FUTURE_LIGHT, FUTURE_DARK):
        control.theme = theme
        assert calls == calls_before
        assert (control.suggestions, control.selected_suggestion, control.selected_text) == state
        assert control.suggestions_open
        assert control._popup_selected == control._popup_selected_foreground == custom
        assert control._popup_border == control._background == custom
        assert control._popup_background == theme.surface_color("surface")
        assert control._popup_foreground == theme.text_color("text")
        assert control._font_family == "Arial"


@pytest.mark.parametrize("theme", [FUTURE_LIGHT, FUTURE_DARK])
def test_builtin_syntax_colors_have_readable_contrast_on_editor_surfaces(theme):
    control = make_control(CodeEditor, theme=theme)

    def luminance(color):
        channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                    for v in (color.r, color.g, color.b)]
        return sum(v * weight for v, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict=True))

    for role in ("raised", "hover"):
        background = luminance(theme.text_color(role))
        for kind, color in control._syntax_colors.items():
            foreground = luminance(color)
            contrast = (max(background, foreground) + 0.05) / (min(background, foreground) + 0.05)
            assert contrast >= 4.5, (theme, kind, role, contrast)


def test_theme_rejects_empty_monospace_family():
    with pytest.raises(ValueError, match="monospace_family"):
        Theme(monospace_family=" ")


def test_themed_selection_uses_plain_foreground_in_legacy_syntax_path():
    control = make_control(CodeEditor, theme=FUTURE_LIGHT)
    control.select(1, 5)  # f Tr, crossing two highlighted tokens
    nodes = list(control.build_scene_node().walk())
    overlays = [n.text for n in nodes if ":syntax:1:" in n.key]
    assert overlays == ["i", "ue"]
    assert control._foreground == FUTURE_LIGHT.text_color("text")


def test_minimap_viewport_is_painted_below_code_marks():
    control = make_control(CodeEditor, theme=FUTURE_LIGHT)
    nodes = list(control.build_scene_node().walk())
    viewport = next(n for n in nodes if n.key.endswith(":minimap:viewport"))
    buckets = [n for n in nodes if ":minimap:bucket:" in n.key]
    assert buckets and all(n.z_index > viewport.z_index for n in buckets)


def test_short_document_minimap_has_compact_rows_and_matching_pointer_mapping():
    control = CodeEditor(
        "\n".join(f"line {i}" for i in range(40)),
        bounds=Rect(0, 0, 500, 400), show_minimap=True,
    )
    nodes = list(control.build_scene_node().walk())
    buckets = [n for n in nodes if ":minimap:bucket:" in n.key]
    bounds = control._minimap_bounds()
    assert buckets[-1].bounds.bottom == bounds.y + 80
    assert buckets[1].bounds.y - buckets[0].bounds.y == 2
    control._scroll_minimap_to_y(bounds.y + 40)
    expected = round((control.line_count - control._visible_line_capacity()) / 2) + 1
    assert control.first_visible_line == expected
    control._scroll_minimap_to_y(bounds.bottom)
    assert control.visible_line_range[1] == 40


def test_popup_selection_respects_first_and_last_rounded_corners():
    control = make_control(Autocomplete, theme=FUTURE_LIGHT)
    selected = next(n for n in control.build_scene_node().walk()
                    if n.key.endswith(":suggestion:0:selected"))
    assert selected.corner_radius.top_left == 11
    assert selected.corner_radius.bottom_left == 0
    control._move_suggestion_selection(1)
    selected = next(n for n in control.build_scene_node().walk()
                    if n.key.endswith(":suggestion:1:selected"))
    assert selected.corner_radius.top_left == 0
    assert selected.corner_radius.bottom_left == 11
