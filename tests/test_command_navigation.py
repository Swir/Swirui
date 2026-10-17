import pytest

from swirui import CommandItem, CommandPalette, ContextMenu, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def send(window, kind, **kwargs):
    window._apply_platform_event(PlatformEvent(kind, NativeWindowHandle(1), **kwargs))


def test_typing_multiword_query_character_by_character_keeps_separator():
    palette = CommandPalette(
        [CommandItem("file", "Open File"), CommandItem("folder", "Open Folder")],
        bounds=Rect(0, 0, 400, 200),
    )
    window = Window(width=400, height=240)
    runtime = mount(window, palette)
    try:
        window.focus_component(palette)
        for char in "open file":
            send(window, PlatformEventKind.TEXT_INPUT, text=char)
        assert palette.query == "open file"
        assert [item.key for item in palette.filtered_items] == ["file"]
    finally:
        runtime.unmount()


@pytest.mark.parametrize("text", ["\x0b", "\b", "\x1b", "\r", "\n", "\t", "\x7f", "\x85"])
def test_palette_rejects_native_shortcut_and_editing_control_characters(text):
    palette = CommandPalette([CommandItem("a", "Action")], bounds=Rect(0, 0, 400, 200))
    window = Window(width=400, height=240)
    runtime = mount(window, palette)
    try:
        window.focus_component(palette)
        send(window, PlatformEventKind.TEXT_INPUT, text=text)
        assert palette.query == ""
        assert palette.active_item.key == "a"
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", [ContextMenu, CommandPalette])
def test_keyboard_reveals_last_command_and_pointer_uses_visible_row(kind):
    control = kind(
        [CommandItem(i, f"Action {i}") for i in range(1000)],
        bounds=Rect(10, 10, 400, 180),
        dismiss_on_invoke=False,
        key="commands",
    )
    window = Window(width=440, height=240)
    runtime = mount(window, control)
    invoked = []
    control.on("command_invoked", lambda event: invoked.append(event.data["key"]))
    try:
        window.focus_component(control)
        send(window, PlatformEventKind.KEY_DOWN, key_code=0x23)
        assert control.active_item.key == 999
        scene = control.build_scene_node()
        labels = [node for node in scene.walk() if node.text == "Action 999"]
        assert len(labels) == 1 and labels[0].bounds.bottom <= control.bounds.bottom
        assert len(list(scene.walk())) < 60
        # A pointer invocation must refer to the rendered row, not its viewport position.
        row = control.row_bounds(999)
        send(
            window,
            PlatformEventKind.POINTER_DOWN,
            x=row.x + 20,
            y=row.y + 12,
            button=PointerButton.LEFT,
        )
        assert invoked == [999]
        send(window, PlatformEventKind.KEY_DOWN, key_code=0x24)
        assert control.active_item.key == 0
        assert any(node.text == "Action 0" for node in control.build_scene_node().walk())
    finally:
        runtime.unmount()
