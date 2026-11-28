"""Editing geometry is tied to shaping, clipping, DPI and theme lifetime."""

import pytest

from swirui import FUTURE_DARK, FUTURE_LIGHT, Button, Input, Label, PasswordInput, Window, mount
from swirui.rendering import Rect
from swirui.rendering.text_layout import NativeTextShaper, TextLineLayout


class ProportionalShaper:
    def __init__(self):
        self.calls = []

    def shape_line(self, text, size, family, scale):
        self.calls.append((text, size, family, scale))
        positions = [0.0]
        for char in text:
            positions.append(positions[-1] + (3.0 if char == "i" else 15.0))
        return TextLineLayout(
            positions[-1] + 1,
            tuple(positions),
            tuple((i, i + 1, positions[i], positions[i + 1]) for i in range(len(text))),
        )


def node(field, suffix):
    return next(n for n in field.build_scene_node().walk() if n.key == field.key + suffix)


def test_button_label_alignment_uses_shaped_width_and_keeps_the_hit_target():
    window = Window()
    button = Button("iiiiW", bounds=Rect(20, 30, 120, 40))
    mount(window, button)
    shaper = ProportionalShaper()
    window._set_text_shaper(shaper)
    assert node(button, ":content").bounds.width == 96  # automatic, full padded width
    for align, x in (("center", 66), ("right", 100), ("left", 32)):
        button.text_align = align
        label = node(button, ":content")
        assert (label.bounds.x, label.bounds.width) == (x, 28)
        assert button.build_scene_node().bounds == Rect(20, 30, 120, 40)
    assert len(shaper.calls) == 1
    button.bounds = Rect(20, 30, 180, 40)
    button.text_align = "center"
    assert node(button, ":content").bounds.x == 96
    assert len(shaper.calls) == 1
    window._set_scale(1.5)
    assert shaper.calls[-1][-1] == 1.5
    button.bounds = Rect(20, 30, 120, 40)
    button.text_align = "left"
    button.text = "WWWWWWWWWW"
    assert node(button, ":content").bounds.width == 96
    button.text = "ii\nsecond line"
    assert node(button, ":content").text == button.text
    assert shaper.calls[-1][0] == "ii"
    with pytest.raises(ValueError, match="text_align"):
        button.text_align = "diagonal"
    assert button.text_align == "left"


def test_fitted_label_reuses_metrics_until_its_font_scale_or_shaper_changes():
    window = Window()
    shaper = ProportionalShaper()
    label = Label("WWW", bounds=Rect(0, 0, 24, 48), font_size=26, min_font_size=14)
    mount(window, label)
    window._set_text_shaper(shaper)
    assert label.build_scene_node().font_size == 14
    calls = len(shaper.calls)
    label.theme = FUTURE_LIGHT
    label.build_scene_node()
    assert len(shaper.calls) == calls
    window._set_scale(1.5)
    assert shaper.calls[-1][-1] == 1.5
    label.font_family = "Consolas"
    assert shaper.calls[-1][-2] == "Consolas"
    replacement = ProportionalShaper()
    window._set_text_shaper(replacement)
    label.text = "iii"
    assert label.build_scene_node().font_size == 26 and replacement.calls[-1][0] == "iii"


def test_proportional_caret_selection_and_click_use_the_same_advances():
    window = Window()
    field = Input("iiiiW", bounds=Rect(0, 0, 240, 44))
    mount(window, field)
    shaper = ProportionalShaper()
    window._set_text_shaper(shaper)
    window.focus_component(field)
    assert node(field, ":caret").bounds.x == 37
    field.select(0, 4)
    assert node(field, ":selection").bounds.width == 12
    assert field._index_from_point(21, 20) == 4
    assert field._index_from_point(36, 20) == 5
    assert len(shaper.calls) == 1  # caret/selection never reshapes unchanged text


def test_long_line_remains_intact_and_scroll_clicks_follow_visible_pixels():
    window = Window()
    field = Input("WWWWiiiiWWWW", bounds=Rect(0, 0, 80, 44))
    mount(window, field)
    window._set_text_shaper(ProportionalShaper())
    window.focus_component(field)
    assert node(field, ":text").text == field.value
    assert node(field, ":text-viewport").clip_to_bounds
    assert node(field, ":caret").bounds.right == pytest.approx(70)
    assert node(field, ":text").bounds.x < 10
    assert field._index_from_point(68.5, 20) == len(field.value)
    field.select(0, 0)
    assert node(field, ":text").bounds.x == 10
    assert node(field, ":caret").bounds.x == 10


def test_shaper_attachment_dpi_and_theme_invalidate_cached_layout():
    window = Window()
    field = Input("iiii", bounds=Rect(0, 0, 200, 44), theme=FUTURE_DARK)
    runtime = mount(window, field)
    window.focus_component(field)
    before = runtime.generation
    shaper = ProportionalShaper()
    window._set_text_shaper(shaper)
    assert runtime.generation > before
    field.theme = FUTURE_LIGHT
    assert field.caret_index == 4
    assert len(shaper.calls) == 1  # color-only theme swap
    window.scale = 1.5
    node(field, ":text")
    assert shaper.calls[-1][-1] == 1.5
    window._set_text_shaper(None)
    assert node(field, ":caret").bounds.x > 22


def test_password_only_supplies_masked_text_to_shaper_and_scene():
    window = Window()
    field = PasswordInput("secret", bounds=Rect(0, 0, 200, 44))
    mount(window, field)
    shaper = ProportionalShaper()
    window._set_text_shaper(shaper)
    assert [call[0] for call in shaper.calls] == ["••••••"]
    assert node(field, ":text").text == "••••••"


def test_visual_selection_keeps_disjoint_bidi_spans_and_collapsed_cluster_empty():
    layout = TextLineLayout(
        40,
        (0, 10, 30, 20, 40),
        (
            (0, 1, 0, 10),
            (1, 2, 30, 40),
            (2, 4, 10, 30),
        ),
    )
    assert layout.selection_spans(0, 2) == ((0, 10), (30, 40))
    assert layout.selection_spans(3, 3) == ()
    assert layout.selection_spans(0, 4) == ((0, 40),)


def test_native_bridge_converts_size_carets_and_segments_at_fractional_dpi():
    class Native:
        def shape_line(self, text, size, family):
            assert (text, size, family) == ("W", 24, "Segoe UI")
            return 19.5, [0, 18], [(0, 1, 0, 18)]

    layout = NativeTextShaper(Native()).shape_line("W", 16, "Segoe UI", 1.5)
    assert layout.width == 13
    assert layout.carets == (0, 12)
    assert layout.selection_spans(0, 1) == ((0, 12),)
