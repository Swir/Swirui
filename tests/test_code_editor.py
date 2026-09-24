from __future__ import annotations

from swirui import AccessibilityRole, CodeEditor
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNodeKind

_WINDOW = NativeWindowHandle(1)


def _event(
    kind: PlatformEventKind,
    *,
    key_code: int | None = None,
    text: str | None = None,
    delta_y: float = 0.0,
    shift: bool = False,
    ctrl: bool = False,
) -> PlatformEvent:
    return PlatformEvent(
        kind=kind,
        window=_WINDOW,
        key_code=key_code,
        text=text,
        delta_y=delta_y,
        shift=shift,
        ctrl=ctrl,
    )


def _syntax_nodes(editor: CodeEditor):
    return [
        node
        for node in editor.build_scene_node().walk()
        if node.kind is SceneNodeKind.TEXT and ":syntax:" in node.key
    ]


def test_code_editor_renders_gutter_current_line_and_accessibility() -> None:
    editor = CodeEditor(
        "alpha\nbeta\ngamma",
        bounds=Rect(12.0, 24.0, 520.0, 180.0),
        font_size=12.0,
        accessible_name="Source editor",
    )
    editor.select(len("alpha\nbe"), len("alpha\nbe"))
    editor.emit("focus_gained")
    scene = editor.build_scene_node()

    keys = {node.key for node in scene.walk()}
    line_numbers = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and ":line-number:" in node.key
    ]

    assert f"{editor.key}:gutter" in keys
    assert f"{editor.key}:gutter-separator" in keys
    assert f"{editor.key}:current-line" in keys
    assert [node.text for node in line_numbers[:3]] == ["1", "2", "3"]
    assert editor.line_count == 3
    assert editor.first_visible_line == 1
    assert editor.accessibility_role is AccessibilityRole.TEXT_BOX
    assert editor.accessible_name == "Source editor"
    assert "caret line 2" in (editor.accessible_value_text or "")


def test_code_editor_tab_shift_tab_undo_and_redo() -> None:
    original = "def render():\nreturn 1"
    editor = CodeEditor(
        original,
        bounds=Rect(0.0, 0.0, 620.0, 220.0),
        tab_size=4,
    )
    line_two = original.index("return")
    editor.select(line_two, line_two)

    tab = editor.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x09),
    )
    assert tab.default_prevented
    assert editor.value == "def render():\n    return 1"
    assert editor.can_undo

    undo = editor.emit(
        "key_down",
        event=_event(
            PlatformEventKind.KEY_DOWN,
            key_code=0x5A,
            ctrl=True,
        ),
    )
    assert undo.default_prevented
    assert editor.value == original
    assert editor.can_redo

    redo = editor.emit(
        "key_down",
        event=_event(
            PlatformEventKind.KEY_DOWN,
            key_code=0x59,
            ctrl=True,
        ),
    )
    assert redo.default_prevented
    assert editor.value == "def render():\n    return 1"

    editor.select(editor.value.index("    return"), editor.value.index("    return"))
    unindent = editor.emit(
        "key_down",
        event=_event(
            PlatformEventKind.KEY_DOWN,
            key_code=0x09,
            shift=True,
        ),
    )
    assert unindent.default_prevented
    assert editor.value == original


def test_code_editor_indents_selected_lines_as_one_edit() -> None:
    editor = CodeEditor(
        "first\nsecond\nthird",
        bounds=Rect(0.0, 0.0, 500.0, 160.0),
        tab_size=2,
    )
    editor.select(0, len("first\nsecond"))
    editor.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x09),
    )

    assert editor.value == "  first\n  second\nthird"
    assert editor.can_undo
    assert editor.undo()
    assert editor.value == "first\nsecond\nthird"


def test_code_editor_virtualizes_large_document_and_scrolls_by_line() -> None:
    document = "\n".join(f"line {index:05d}" for index in range(10_000))
    editor = CodeEditor(
        document,
        bounds=Rect(0.0, 0.0, 720.0, 150.0),
        font_size=10.0,
        padding=6.0,
    )

    assert editor.scroll_to_line(5_000)
    assert editor.first_visible_line == 5_000
    scene = editor.build_scene_node()
    line_numbers = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and ":line-number:" in node.key
    ]

    assert 1 <= len(line_numbers) <= 12
    assert line_numbers[0].text == "5000"
    assert len(list(scene.walk())) <= 32
    assert editor.visible_line_range[0] == 5_000

    before = editor.first_visible_line
    scroll = editor.emit(
        "pointer_scroll",
        event=_event(
            PlatformEventKind.POINTER_SCROLL,
            delta_y=editor._line_height() * 3.0,
        ),
    )
    assert scroll.default_prevented
    assert editor.first_visible_line == before + 3


def test_code_editor_can_hide_line_numbers_without_losing_editing_surface() -> None:
    editor = CodeEditor(
        "alpha\nbeta",
        bounds=Rect(0.0, 0.0, 420.0, 120.0),
        show_line_numbers=False,
    )
    scene = editor.build_scene_node()

    assert all(":gutter" not in node.key for node in scene.walk())
    editor.emit(
        "text_input",
        event=_event(PlatformEventKind.TEXT_INPUT, text="\ngamma"),
    )
    assert editor.value.endswith("\ngamma")


def test_python_syntax_highlighting_colors_core_tokens_and_multiline_strings() -> None:
    source = (
        "@decorator\n"
        "def render(value: int = 42):\n"
        "    text = \"\"\"alpha\n"
        "beta\"\"\"\n"
        "    return True  # ready\n"
    )
    editor = CodeEditor(
        source,
        bounds=Rect(0.0, 0.0, 760.0, 260.0),
        language="python",
    )
    nodes = _syntax_nodes(editor)
    texts = {node.text for node in nodes}
    kinds = {node.key.rsplit(":", 1)[-1] for node in nodes}

    assert {"decorator", "def", "render", "42", "return", "True", "# ready"} <= texts
    assert "beta\"\"\"" in texts
    assert {"decorator", "keyword", "definition", "number", "string", "literal", "comment"} <= kinds
    assert "syntax python" in (editor.accessible_value_text or "")


def test_json_syntax_highlighting_distinguishes_keys_values_and_literals() -> None:
    editor = CodeEditor(
        '{"name": "SwirUI", "ready": true, "count": 68}',
        bounds=Rect(0.0, 0.0, 760.0, 120.0),
        language="json",
    )
    nodes = _syntax_nodes(editor)
    by_text = {node.text: node.key.rsplit(":", 1)[-1] for node in nodes}

    assert by_text['"name"'] == "key"
    assert by_text['"SwirUI"'] == "string"
    assert by_text['"ready"'] == "key"
    assert by_text["true"] == "literal"
    assert by_text["68"] == "number"


def test_syntax_highlighting_can_toggle_change_language_and_override_colors() -> None:
    custom_keyword = Color.from_hex("#FFFFFF")
    editor = CodeEditor(
        "def build():\n    return None",
        bounds=Rect(0.0, 0.0, 540.0, 160.0),
        language="py",
        syntax_colors={"keyword": custom_keyword},
    )
    keyword_nodes = [
        node for node in _syntax_nodes(editor) if node.key.endswith(":keyword")
    ]
    assert keyword_nodes
    assert all(node.fill == custom_keyword for node in keyword_nodes)
    assert editor.language == "python"

    editor.syntax_highlighting = False
    assert not _syntax_nodes(editor)
    editor.syntax_highlighting = True
    editor.language = "json"
    editor.value = '{"ok": false}'
    assert any(node.text == "false" for node in _syntax_nodes(editor))


def test_syntax_highlighting_is_viewport_bounded_for_large_python_document() -> None:
    document = "\n".join(
        f"def generated_{index:05d}(): return {index}" for index in range(10_000)
    )
    editor = CodeEditor(
        document,
        bounds=Rect(0.0, 0.0, 720.0, 150.0),
        font_size=10.0,
        padding=6.0,
        language="python",
    )
    editor.scroll_to_line(5_000)
    scene = editor.build_scene_node()
    syntax_nodes = [node for node in scene.walk() if ":syntax:" in node.key]

    assert syntax_nodes
    assert len(syntax_nodes) <= 64
    assert all(5_000 <= int(node.key.split(":syntax:", 1)[1].split(":", 1)[0]) <= 5_012 for node in syntax_nodes)
    assert len(list(scene.walk())) <= 96


def test_incomplete_python_source_keeps_successful_highlights_without_raising() -> None:
    editor = CodeEditor(
        "def unfinished(\n    value = \"open",
        bounds=Rect(0.0, 0.0, 620.0, 180.0),
        language="python",
    )
    nodes = _syntax_nodes(editor)

    assert any(node.text == "def" for node in nodes)
    assert any(node.text == "unfinished" for node in nodes)


def test_code_editor_rejects_invalid_configuration() -> None:
    bounds = Rect(0.0, 0.0, 400.0, 160.0)

    try:
        CodeEditor(bounds=bounds, tab_size=0)
    except ValueError as exc:
        assert "tab_size" in str(exc)
    else:
        raise AssertionError("tab_size=0 should fail")

    try:
        CodeEditor(bounds=bounds, undo_limit=0)
    except ValueError as exc:
        assert "undo_limit" in str(exc)
    else:
        raise AssertionError("undo_limit=0 should fail")

    try:
        CodeEditor(bounds=bounds, language="javascript")
    except ValueError as exc:
        assert "language" in str(exc)
    else:
        raise AssertionError("unsupported language should fail")
