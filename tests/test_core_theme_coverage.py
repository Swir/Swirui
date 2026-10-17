"""Theme changes must preserve working controls, not only recolor static samples."""

from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Accordion,
    Badge,
    Chip,
    Component,
    Dialog,
    Expander,
    GlassCard,
    Input,
    Label,
    ProgressBar,
    ProgressRing,
    ScrollView,
    SplitView,
    Toast,
    Tooltip,
    Window,
    mount,
)
from swirui.core import Event
from swirui.rendering import Color, FrostedGlass, Rect, SceneNodeKind

BOUNDS = Rect(0, 0, 240, 44)


def child(widget, suffix):
    return next(node for node in widget.build_scene_node().walk() if node.key.endswith(suffix))


@pytest.mark.parametrize("factory", [ProgressBar, ProgressRing])
def test_progress_inherits_palette_without_resetting_value_or_accessibility(factory):
    root = Component(theme=FUTURE_DARK)
    progress = factory(bounds=BOUNDS, value=37)
    legacy = [node.fill for node in progress.build_scene_node().walk()]
    root.add(progress)
    changes = []
    progress.on("changed", changes.append)
    for theme in (FUTURE_LIGHT, FUTURE_DARK):
        root.theme = theme
        colors = {node.fill for node in progress.build_scene_node().walk()}
        assert theme.surface_color("accent") in colors
        assert theme.surface_color("border") in colors
        assert progress.value == progress.accessible_value == 37
        assert progress.accessible_value_text == "37%"
    progress.enabled = False
    assert all(
        node.fill == FUTURE_DARK.surface_color("disabled")
        for node in progress.build_scene_node().walk()
        if node.kind is not SceneNodeKind.GROUP
    )
    progress.enabled = True
    root.remove(progress)
    assert [node.fill for node in progress.build_scene_node().walk()] == legacy
    assert changes == []


@pytest.mark.parametrize("theme", [FUTURE_DARK, FUTURE_LIGHT])
def test_selected_chip_keeps_paired_colors_across_hover_press_focus_and_disable(theme):
    chip = Chip("Pinned", bounds=BOUNDS, selected=True, theme=theme)
    window = Window()
    runtime = mount(window, chip)
    try:
        assert chip.build_scene_node().fill == theme.surface_color("accent")
        chip.dispatch(Event("pointer_enter", chip))
        assert chip.build_scene_node().fill == theme.surface_color("accent_hover")
        assert child(chip, ":content").fill == theme.text_color("on_accent")
        chip._set_interaction_state(pressed=True, reason="key_down")
        assert chip.build_scene_node().fill == theme.surface_color("accent_pressed")
        chip._set_interaction_state(pressed=False, reason="key_up")
        window.focus_component(chip)
        assert chip.build_scene_node().fill == theme.surface_color("focus")
        assert child(chip, ":focus-surface").fill == theme.surface_color("accent_hover")
        assert chip.selected and chip.accessible_checked
        chip.enabled = False
        assert chip.build_scene_node().fill == theme.surface_color("disabled")
        assert child(chip, ":content").fill == theme.text_color("disabled_text")
    finally:
        runtime.unmount()


def test_authored_badge_and_chip_styles_survive_theme_changes():
    custom = Color(0.2, 0.3, 0.4)
    root = Component(theme=FUTURE_DARK)
    badge = Badge("Stable", bounds=BOUNDS, corner_radius=0, font_family="Arial")
    chip = Chip(
        "Stable",
        bounds=BOUNDS,
        selected=True,
        selected_background=custom,
        selected_foreground=custom,
    )
    root.add(badge, chip)
    # Assigning even the currently resolved value establishes author intent.
    badge.background = badge.background
    badge.foreground = badge.foreground
    original = (badge.background, badge.foreground)
    root.theme = FUTURE_LIGHT
    assert (badge.background, badge.foreground) == original
    assert badge.build_scene_node().corner_radius.top_left == 0
    assert child(badge, ":text").font_family == "Arial"
    chip.dispatch(Event("pointer_enter", chip))
    assert chip.build_scene_node().fill == custom
    assert child(chip, ":content").fill == custom


def test_collapsed_content_and_open_tooltip_recolor_without_state_events():
    field = Input("Persistent text", bounds=BOUNDS)
    expander = Expander("Details", bounds=BOUNDS, content=field)
    accordion = Accordion(expander, theme=FUTURE_DARK)
    tip = Tooltip("Help", bounds=BOUNDS, initially_open=True)
    root = Component(theme=FUTURE_DARK).add(accordion, tip)
    changes = []
    expander.on("expanded_changed", changes.append)
    accordion.theme = None
    root.theme = FUTURE_LIGHT
    assert not field.visible and not expander.expanded
    assert tip.is_open
    assert tip.build_scene_node().fill == FUTURE_LIGHT.surface_color("raised")
    assert child(tip, ":text").fill == FUTURE_LIGHT.text_color("text")
    assert field.effective_theme == FUTURE_LIGHT
    assert child(expander, ":indicator").fill == FUTURE_LIGHT.text_color("accent")
    assert changes == []
    expander.expand()
    assert field.visible and field.value == "Persistent text"


def test_expander_has_visible_keyboard_focus_in_both_modes():
    expander = Expander("Options", bounds=BOUNDS, theme=FUTURE_DARK)
    window = Window()
    runtime = mount(window, expander)
    try:
        window.focus_component(expander)
        for theme in (FUTURE_DARK, FUTURE_LIGHT):
            expander.theme = theme
            assert expander.build_scene_node().fill == theme.surface_color("focus")
            assert child(expander, ":focus-surface").fill == theme.surface_color("hover")
        expander.enabled = False
        assert child(expander, ":title").fill == FUTURE_LIGHT.text_color("disabled_text")
    finally:
        runtime.unmount()


def test_theme_changes_preserve_split_scroll_dialog_and_notification_lifetime():
    field = Input("Keep me", bounds=BOUNDS)
    scrolling = ScrollView(bounds=Rect(0, 0, 260, 100), content_height=500)
    scrolling.add(field)
    scrolling.scroll_to(y=60)
    split = SplitView(
        bounds=Rect(0, 0, 600, 200),
        first=scrolling,
        second=Label("Other", bounds=BOUNDS),
        split_ratio=0.4,
    )
    dialog = Dialog(
        bounds=Rect(0, 0, 640, 400), dialog_bounds=Rect(20, 20, 600, 240), content=split
    )
    toast = Toast("Still saving", bounds=Rect(0, 280, 300, 90), duration_seconds=5)
    toast.advance(2)
    root = Component(theme=FUTURE_DARK).add(dialog, toast)
    window = Window(width=640, height=400)
    runtime = mount(window, root)
    window.focus_component(split)
    changes = []
    window.on("scene_changed", changes.append)
    try:
        root.theme = FUTURE_LIGHT
        assert len(changes) == 1
        assert window.focused_component is split
        assert split.split_ratio == 0.4 and scrolling.scroll_y == 60
        assert dialog.is_open and dialog.content is split and split.first is scrolling
        assert field.value == "Keep me"
        assert toast.elapsed_seconds == 2 and toast.visible
        assert child(toast, ":surface").fill == FUTURE_LIGHT.surface_color("raised")
        assert child(toast, ":message").fill == FUTURE_LIGHT.text_color("muted")
        assert child(dialog, ":surface").fill == FUTURE_LIGHT.surface_color("surface")
    finally:
        runtime.unmount()


@pytest.mark.parametrize(
    "kind,role",
    [("info", "accent"), ("success", "success"), ("warning", "warning"), ("error", "error")],
)
def test_toast_kind_uses_semantic_colors_in_custom_themes(kind, role):
    custom = replace(
        FUTURE_LIGHT,
        palette=replace(FUTURE_LIGHT.palette, warning="#765400", error="#A82739"),
        font_family="Arial",
    )
    toast = Toast("Message", bounds=Rect(0, 0, 300, 90), kind=kind, theme=custom)
    assert child(toast, ":accent").fill == custom.surface_color(role)
    assert child(toast, ":title").font_family == "Arial"
    toast.theme = FUTURE_DARK
    assert child(toast, ":accent").fill == FUTURE_DARK.surface_color(role)
    toast.kind = "error"
    assert child(toast, ":accent").fill == FUTURE_DARK.surface_color("error")


def test_glass_theme_tracks_palette_but_explicit_material_wins():
    glass = GlassCard(bounds=BOUNDS)
    legacy = glass.material
    glass.theme = FUTURE_LIGHT
    assert glass.material.tint == Color(1, 1, 1, 0.66)
    assert glass.material.corner_radius.top_left == FUTURE_LIGHT.control_radius
    glass.theme = None
    assert glass.material == legacy
    authored = FrostedGlass(blur_radius=8)
    glass.material = authored
    glass.theme = FUTURE_DARK
    assert glass.material is authored
    scoped = GlassCard(bounds=BOUNDS, theme=FUTURE_LIGHT, material=authored)
    assert scoped.material is authored


@pytest.mark.parametrize(
    "factory",
    [
        lambda **kw: Badge("Badge", **kw),
        lambda **kw: Tooltip("Tooltip", **kw),
        lambda **kw: Expander("Expander", **kw),
    ],
)
def test_geometry_font_overrides_are_validated_and_preserved(factory):
    for kwargs in ({"corner_radius": -1}, {"font_family": " "}):
        with pytest.raises(ValueError):
            factory(bounds=BOUNDS, theme=FUTURE_DARK, **kwargs)
    widget = factory(bounds=BOUNDS, theme=FUTURE_LIGHT, corner_radius=3, font_family=" Arial ")
    widget.theme = FUTURE_DARK
    node = widget.build_scene_node()
    assert node.corner_radius.top_left == 3
    assert all(n.font_family == "Arial" for n in node.walk() if n.kind is SceneNodeKind.TEXT)
