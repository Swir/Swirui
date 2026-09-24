from __future__ import annotations

from swirui import AccessibilityRole, Terminal
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind

_WINDOW = NativeWindowHandle(1)


def _event(
    kind: PlatformEventKind,
    *,
    key_code: int | None = None,
    text: str | None = None,
) -> PlatformEvent:
    return PlatformEvent(kind=kind, window=_WINDOW, key_code=key_code, text=text)


def test_terminal_scrollback_is_bounded_and_clear_buffer_preserves_component_api() -> None:
    terminal = Terminal(bounds=Rect(0.0, 0.0, 420.0, 180.0), max_lines=3)

    for index in range(5):
        terminal.writeln(f"line-{index}")

    assert terminal.lines == ("line-2", "line-3", "line-4")
    terminal.clear_buffer()
    assert terminal.lines == ()

    # Terminal intentionally keeps Component.clear() available for child management.
    terminal.clear()
    assert terminal.children == []


def test_terminal_handles_ansi_spans_without_leaking_escape_sequences() -> None:
    terminal = Terminal(bounds=Rect(0.0, 0.0, 500.0, 120.0), font_size=12.0)
    terminal.write("\x1b[31mred")
    terminal.write("\x1b[0m normal")
    scene = terminal.build_scene_node()

    text_nodes = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and ":line:" in node.key
    ]
    assert [node.text for node in text_nodes] == ["red", " normal"]
    assert text_nodes[0].fill != text_nodes[1].fill
    assert all("\x1b" not in (node.text or "") for node in text_nodes)


def test_terminal_edit_submit_and_history_navigation() -> None:
    terminal = Terminal(bounds=Rect(0.0, 0.0, 480.0, 180.0), prompt="$ ")
    submitted: list[str] = []
    terminal.on("submitted", lambda event: submitted.append(str(event.data["command"])))

    terminal.emit(
        "text_input",
        platform_event=_event(PlatformEventKind.TEXT_INPUT, text="echo hello"),
    )
    assert terminal.input_text == "echo hello"

    terminal.emit(
        "key_down",
        platform_event=_event(PlatformEventKind.KEY_DOWN, key_code=0x25),
    )
    terminal.emit(
        "key_down",
        platform_event=_event(PlatformEventKind.KEY_DOWN, key_code=0x08),
    )
    assert terminal.input_text == "echo helo"
    assert terminal.caret_index == len("echo hel")

    terminal.input_text = "echo hello"
    enter = terminal.emit(
        "key_down",
        platform_event=_event(PlatformEventKind.KEY_DOWN, key_code=0x0D),
    )
    assert enter.default_prevented
    assert submitted == ["echo hello"]
    assert terminal.lines[-1] == "$ echo hello"
    assert terminal.input_text == ""

    terminal.emit(
        "key_down",
        platform_event=_event(PlatformEventKind.KEY_DOWN, key_code=0x26),
    )
    assert terminal.input_text == "echo hello"
    terminal.emit(
        "key_down",
        platform_event=_event(PlatformEventKind.KEY_DOWN, key_code=0x28),
    )
    assert terminal.input_text == ""


def test_terminal_scene_virtualizes_scrollback_and_exposes_accessibility() -> None:
    terminal = Terminal(
        bounds=Rect(12.0, 24.0, 360.0, 92.0),
        max_lines=500,
        font_size=10.0,
        padding=4.0,
        accessible_name="Build console",
    )
    for index in range(120):
        terminal.writeln(f"build line {index:03d}")

    terminal.emit("focus_gained")
    scene = terminal.build_scene_node()
    output_nodes = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and ":line:" in node.key
    ]

    assert 1 <= len(output_nodes) <= 5
    assert output_nodes[-1].text == "build line 119"
    assert terminal.focusable
    assert terminal.focused
    assert terminal.accessibility_role is AccessibilityRole.TEXT_BOX
    assert terminal.accessible_name == "Build console"
    assert "build line 119" in (terminal.accessible_value_text or "")
    assert any(node.key.endswith(":caret") for node in scene.walk())


def test_terminal_preserves_incomplete_ansi_sequence_across_writes() -> None:
    terminal = Terminal(bounds=Rect(0.0, 0.0, 420.0, 100.0))
    terminal.write("\x1b[3")
    terminal.write("2mgreen")

    assert terminal.lines == ("green",)
    scene = terminal.build_scene_node()
    assert all("\x1b" not in (node.text or "") for node in scene.walk())
