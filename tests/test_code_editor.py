from __future__ import annotations

from swirui import AccessibilityRole, CodeEditor
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Rect
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
