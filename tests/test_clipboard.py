import pytest

from swirui import (
    ClipboardError,
    CodeEditor,
    Input,
    MemoryClipboard,
    PasswordInput,
    TextArea,
    Window,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Rect

BOUNDS = Rect(0, 0, 300, 100)


def key(window: Window, value: str, *, ctrl: bool = True) -> None:
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=ord(value), ctrl=ctrl
        )
    )


def attach(field: Input | TextArea, clipboard: MemoryClipboard) -> Window:
    window = Window(clipboard=clipboard)
    window.set_root(field)
    window.focus_component(field)
    return window


def test_copy_cut_paste_preserve_unicode_and_selection() -> None:
    clipboard = MemoryClipboard()
    field = Input("Zażółć 🌍", bounds=BOUNDS)
    window = attach(field, clipboard)
    key(window, "A")
    key(window, "C")
    assert clipboard.read_text() == "Zażółć 🌍"
    assert field.selected_text == "Zażółć 🌍"
    key(window, "X")
    assert field.value == ""
    key(window, "V")
    assert field.value == "Zażółć 🌍"
    assert field.caret_index == len(field.value)
    assert not field.selected_text


def test_paste_replaces_only_selection_and_obeys_max_length() -> None:
    field = Input("abcdef", bounds=BOUNDS, max_length=8)
    window = attach(field, MemoryClipboard("123456789"))
    field._move_caret(2, extend=False)
    field._move_caret(4, extend=True)
    key(window, "V")
    assert field.value == "ab1234ef"
    assert field.caret_index == 6


@pytest.mark.parametrize("contents", [None, "", "\x01\x02"])
def test_non_text_empty_and_filtered_paste_do_not_delete_selection(contents: str | None) -> None:
    field = Input("keep", bounds=BOUNDS)
    window = attach(field, MemoryClipboard(contents))
    key(window, "A")
    key(window, "V")
    assert field.value == field.selected_text == "keep"


def test_read_only_can_copy_but_cannot_cut_or_paste() -> None:
    clipboard = MemoryClipboard("old")
    field = Input("read only", bounds=BOUNDS, read_only=True)
    window = attach(field, clipboard)
    key(window, "A")
    key(window, "X")
    assert clipboard.read_text() == "old"
    key(window, "V")
    assert field.value == "read only"
    key(window, "C")
    assert clipboard.read_text() == "read only"


def test_password_never_exports_secret_but_accepts_paste() -> None:
    clipboard = MemoryClipboard("replacement")
    field = PasswordInput("secret", bounds=BOUNDS)
    window = attach(field, clipboard)
    key(window, "A")
    for command in ("C", "X"):
        key(window, command)
        assert clipboard.read_text() == "replacement"
        assert field.value == "secret"
    key(window, "V")
    assert field.value == "replacement"


def test_multiline_paste_and_code_editor_undo_are_one_edit() -> None:
    clipboard = MemoryClipboard("one\r\n\ttwo\rthree")
    editor = CodeEditor("original", bounds=BOUNDS)
    window = attach(editor, clipboard)
    key(window, "A")
    key(window, "V")
    assert editor.value == "one\n\ttwo\nthree"
    key(window, "Z")
    assert editor.value == "original"
    key(window, "Y")
    assert editor.value == "one\n\ttwo\nthree"


def test_failed_cut_preserves_value_selection_and_reports_error() -> None:
    class BusyClipboard(MemoryClipboard):
        def write_text(self, text: str) -> None:
            raise ClipboardError("busy")

    field = Input("keep", bounds=BOUNDS)
    window = attach(field, BusyClipboard())
    errors = []
    field.on("clipboard_error", errors.append)
    key(window, "A")
    key(window, "X")
    assert field.value == field.selected_text == "keep"
    assert errors[0].data["operation"] == "cut"


def test_missing_provider_reports_unavailable_without_modifying_input() -> None:
    field = Input("keep", bounds=BOUNDS)
    window = Window().set_root(field)
    window.focus_component(field)
    errors = []
    field.on("clipboard_error", errors.append)
    key(window, "A")
    key(window, "X")
    assert field.selected_text == "keep"
    assert isinstance(errors[0].data["error"], ClipboardError)


def test_shared_clipboard_and_capture_cancellation() -> None:
    clipboard = MemoryClipboard("shared")
    first = attach(Input(bounds=BOUNDS), clipboard)
    second = attach(Input(bounds=BOUNDS), clipboard)
    first.set_clipboard_text("from first")
    key(second, "V")
    assert second.root.value == "from first"
    second.root.on("key_down", lambda event: event.stop_propagation(), capture=True)
    first.set_clipboard_text("cancelled")
    key(second, "V")
    assert second.root.value == "from first"


@pytest.mark.parametrize("text", ["bad\0text", "\ud800"])
def test_invalid_clipboard_text_does_not_replace_previous_contents(text: str) -> None:
    clipboard = MemoryClipboard("keep")
    with pytest.raises(ClipboardError):
        clipboard.write_text(text)
    assert clipboard.read_text() == "keep"
