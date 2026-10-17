import pytest

from swirui import ClipboardError, CommandItem, CommandPalette, MemoryClipboard, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Rect


def key(window, code, **modifiers):
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=code, **modifiers)
    )


def text(window, value):
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.TEXT_INPUT, NativeWindowHandle(1), text=value)
    )


@pytest.fixture
def editor():
    clipboard = MemoryClipboard("Open asset")
    palette = CommandPalette(
        [CommandItem("asset", "Open asset"), CommandItem("file", "Open file")],
        bounds=Rect(0, 0, 420, 240),
        dismiss_on_invoke=False,
    )
    window = Window(width=500, height=300, clipboard=clipboard)
    runtime = mount(window, palette)
    window.focus_component(palette)
    yield palette, window, clipboard
    runtime.unmount()


def test_paste_copy_cut_replacement_and_filter_events(editor):
    palette, window, clipboard = editor
    queries = []
    palette.on("query_changed", lambda event: queries.append(event.data["query"]))
    key(window, 0x56, ctrl=True)
    assert palette.query == "Open asset" and palette.active_item.key == "asset"
    key(window, 0x41, ctrl=True)
    key(window, 0x43, ctrl=True)
    assert clipboard.read_text() == palette.selected_text == "Open asset"
    key(window, 0x58, ctrl=True)
    assert palette.query == "" and len(palette.filtered_items) == 2
    text(window, "Open file")
    key(window, 0x41, ctrl=True)
    key(window, 0x56, ctrl=True)
    assert palette.query == "Open asset"
    assert queries == ["Open asset", "", "Open file", "Open asset"]


def test_caret_selection_delete_and_query_boundary_keys(editor):
    palette, window, _ = editor
    palette.set_query("Open Xasset")
    key(window, 0x24, ctrl=True)
    for _ in range(5):
        key(window, 0x27)
    key(window, 0x2E)
    assert palette.query == "Open asset" and palette.caret_index == 5
    key(window, 0x23, shift=True)
    assert palette.selected_text == "asset"
    text(window, "file")
    assert palette.query == "Open file" and palette.active_item.key == "file"
    key(window, 0x08)
    assert palette.query == "Open fil"


def test_plain_home_end_keep_result_navigation_without_changing_caret(editor):
    palette, window, _ = editor
    palette.set_query("Open")
    key(window, 0x25)
    caret = palette.caret_index
    key(window, 0x23)
    assert palette.active_item.key == "file" and palette.caret_index == caret
    key(window, 0x24)
    assert palette.active_item.key == "asset" and palette.caret_index == caret


def test_failed_cut_keeps_selected_query_and_reports_error(editor):
    palette, window, _ = editor

    class BrokenClipboard:
        def read_text(self):
            raise ClipboardError("read failed")

        def write_text(self, value):
            raise ClipboardError("write failed")

    window._clipboard = BrokenClipboard()
    palette.set_query("Keep me")
    errors = []
    palette.on("clipboard_error", lambda event: errors.append(event.data["operation"]))
    key(window, 0x41, ctrl=True)
    key(window, 0x58, ctrl=True)
    assert palette.query == palette.selected_text == "Keep me"
    assert errors == ["cut"]


def test_multiline_paste_becomes_query_words_and_removes_control_codes(editor):
    palette, window, clipboard = editor
    clipboard.write_text("Open\r\nasset\t\x0b\x85")
    key(window, 0x56, ctrl=True)
    assert palette.query == "Open asset " and palette.active_item.key == "asset"


def test_initial_query_and_equivalent_assignment_filter_the_displayed_text():
    palette = CommandPalette(
        [CommandItem("asset", "Open asset")], query="Open\x01\nasset", bounds=Rect(0, 0, 420, 240)
    )
    assert palette.query == "Open asset" and palette.active_item.key == "asset"
    palette.select_all()
    palette.set_query("Open\x01\nasset")
    assert palette.selected_text == "Open asset"
