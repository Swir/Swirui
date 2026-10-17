"""Proportional multiline geometry, visual navigation and bounded shaping."""

from swirui import CodeEditor, TextArea, Window, mount
from swirui.rendering import Rect, SceneNodeKind
from swirui.rendering.text_layout import TextLineLayout


class Shaper:
    supports_color_spans = True

    def __init__(self):
        self.calls = []

    def shape_line(self, text, size, family, scale):
        assert not any(char in text for char in "\r\n\u2028\u2029")
        self.calls.append(text)
        carets = [0.0]
        for char in text:
            carets.append(carets[-1] + (3 if char == "i" else 15))
        return TextLineLayout(
            carets[-1] + 1,
            tuple(carets),
            tuple((i, i + 1, carets[i], carets[i + 1]) for i in range(len(text))),
        )


def setup(text, cls=TextArea, **kwargs):
    field = cls(text, bounds=Rect(0, 0, 140, 100), **kwargs)
    window = Window()
    mount(window, field)
    shaper = Shaper()
    window._set_text_shaper(shaper)
    window.focus_component(field)
    return window, field, shaper


def test_rows_keep_whole_text_in_content_clip_and_scroll_to_long_caret():
    _, area, _ = setup("WWWWWWWWWWWW\niiii")
    area.select(12, 12)
    nodes = {n.key: n for n in area.build_scene_node().walk()}
    assert nodes[area.key + ":text:0"].text == "W" * 12
    assert nodes[area.key + ":text:0"].bounds.x < 10
    assert nodes[area.key + ":caret"].bounds.right == 130
    assert nodes[area.key + ":text-viewport"].clip_to_bounds
    assert area._index_from_point(128.5, 15) == 12


def test_vertical_navigation_preserves_visual_column_across_short_lines():
    _, area, _ = setup("WW\ni\niiiiiiiiii")
    area.select(2, 2)  # x=30
    area._move_vertical(1, extend=False)
    assert area.caret_index == 4  # clamp to x=3 without discarding desired x=30
    area._move_vertical(1, extend=True)
    assert area.caret_index == len(area.value)
    assert area.selected_text == "\niiiiiiiiii"
    area._move_vertical(-2, extend=False)
    assert area.caret_index == 2
    area._move_horizontal(-1, extend=False)
    area._move_vertical(2, extend=False)
    assert area.caret_index == 10  # explicit horizontal move resets desired x to 15


def test_multiline_selection_and_clicks_follow_individual_line_advances():
    _, area, _ = setup("iiii\nWW")
    area.select(0, len(area.value))
    selections = [n for n in area.build_scene_node().walk() if ":selection:" in n.key]
    assert selections[0].bounds.width == 12
    assert selections[-1].bounds.width == 30
    assert area._index_from_point(21, 15) == 4
    assert area._index_from_point(26, 40) == 6


def test_large_document_shapes_only_viewport_and_reuses_layouts():
    _, area, shaper = setup("\n".join(f"row {i}" for i in range(20_000)))
    area.build_scene_node()
    before = len(shaper.calls)
    for _ in range(3):
        area.build_scene_node()
    assert len(shaper.calls) == before
    assert before < 12
    assert len(area._multiline_layouts) <= 128


def test_shaping_cache_is_bounded_by_entries_and_total_characters():
    _, area, _ = setup("")
    for i in range(200):
        area._multiline_layout(f"{i}" + "i" * 600)
    assert len(area._multiline_layouts) <= 128
    assert area._multiline_layout_chars <= 65_536


def test_code_colors_share_complete_shaped_lines_without_duplicate_glyphs():
    _, editor, _ = setup("if iii:\n    return 42", CodeEditor, language="python")
    editor.bounds = Rect(0, 0, 480, 120)
    nodes = list(editor.build_scene_node().walk())
    lines = [n for n in nodes if n.kind is SceneNodeKind.TEXT and ":text:" in n.key]
    assert len(lines) == 2
    assert lines[0].text_spans[0][:2] == (0, 2)
    assert lines[1].text_spans[-1][:2] == (11, 13)
    assert not any(":syntax:" in n.key for n in nodes)
    editor.select(len(editor.value), len(editor.value))
    editor.syntax_highlighting = False
    assert not any(n.text_spans for n in editor.build_scene_node().walk())


def test_code_keyboard_scroll_rebuilds_visible_rows_in_same_input_event():
    window, editor, _ = setup("\n".join(f"line {i}" for i in range(30)), CodeEditor)
    editor._move_caret(0, extend=False)
    editor._move_page(1, extend=False)
    assert editor.first_visible_line > 1
    assert any(n.key == editor.key + ":caret" for n in window.scene.walk())


def test_placeholder_normalizes_windows_and_unicode_line_endings_before_shaping():
    _, area, shaper = setup("", placeholder="First\r\nSecond\u2028Third")
    assert [n.text for n in area.build_scene_node().walk() if n.kind is SceneNodeKind.TEXT] == [
        "First",
        "Second",
        "Third",
    ]
    assert "Second" in shaper.calls


def test_detached_control_releases_font_provider_and_document_layout_cache():
    window, area, _ = setup("iiii\nWWWW")
    assert area._multiline_layouts
    window.set_root(None)
    assert not area.mounted
    assert not area._multiline_layouts
    assert area._multiline_layout_chars == 0
    assert area._line_layout_key is None
    assert area._document_cache_value is None
