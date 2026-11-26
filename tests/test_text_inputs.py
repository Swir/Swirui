import pytest

from swirui import CodeEditor, Component, Input, PasswordInput, TextArea, Window, mount
from swirui.core import AccessibilityRole, Event
from swirui.platforms import (
    NativeWindowHandle,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)
from swirui.rendering import Point, Rect, Scene, SceneNode, SceneNodeKind
from swirui.widgets import compile_component_scene


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def _send(
    window: Window,
    kind: PlatformEventKind,
    *,
    key_code: int | None = None,
    text: str | None = None,
    shift: bool = False,
    ctrl: bool = False,
) -> None:
    window._apply_platform_event(
        PlatformEvent(
            kind,
            NativeWindowHandle(1),
            key_code=key_code,
            text=text,
            shift=shift,
            ctrl=ctrl,
        )
    )


def test_input_compiles_retained_textbox_placeholder_and_semantics() -> None:
    root = Component("root")
    field = Input(
        key="username",
        bounds=Rect(20.0, 24.0, 240.0, 44.0),
        placeholder="Username",
        accessible_name="User name",
    )
    root.add(field)

    scene = compile_component_scene(root, width=420.0, height=220.0)

    assert scene is not None
    input_node = _node(scene, "username")
    text_node = _node(scene, "username:text")
    assert input_node.kind is SceneNodeKind.RECTANGLE
    assert input_node.hit_testable is True
    assert text_node.kind is SceneNodeKind.TEXT
    assert text_node.text == "Username"
    assert text_node.hit_testable is False
    assert scene.hit_test(Point(40.0, 40.0)) is input_node
    assert field.focusable is True
    assert field.accessibility_role is AccessibilityRole.TEXT_BOX
    assert field.accessible_name == "User name"


def test_input_routes_text_editing_selection_delete_and_submit() -> None:
    window = Window(width=420, height=220)
    root = Component("root")
    field = Input(
        key="query",
        bounds=Rect(20.0, 24.0, 240.0, 44.0),
        max_length=6,
    )
    root.add(field)
    runtime = mount(window, root)
    changed: list[Event] = []
    submitted: list[Event] = []
    field.on("changed", changed.append)
    field.on("submitted", submitted.append)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=40.0,
            y=40.0,
            button=PointerButton.LEFT,
        )
    )
    assert window.focused_component is field
    assert field.focused is True

    _send(window, PlatformEventKind.TEXT_INPUT, text="hello")
    assert field.value == "hello"
    assert len(changed) == 1

    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x25, shift=True)
    assert field.selected_text == "o"
    _send(window, PlatformEventKind.TEXT_INPUT, text="!")
    assert field.value == "hell!"

    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x41, ctrl=True)
    assert field.selected_text == "hell!"
    _send(window, PlatformEventKind.TEXT_INPUT, text="SwirUI rocks")
    assert field.value == "SwirUI"
    assert field.selected_text == ""

    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x08)
    assert field.value == "SwirU"
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x0D)
    assert len(submitted) == 1
    assert submitted[0].data["value"] == "SwirU"
    assert runtime.generation >= 7


def test_password_input_never_places_plaintext_in_scene_nodes() -> None:
    field = PasswordInput(
        "secret",
        key="password",
        bounds=Rect(10.0, 10.0, 220.0, 44.0),
        accessible_name="Password",
    )

    node = field.build_scene_node()
    texts = [child.text for child in node.walk() if child.kind is SceneNodeKind.TEXT]

    assert field.value == "secret"
    assert field.accessibility_role is AccessibilityRole.PASSWORD_BOX
    assert texts == ["••••••"]
    assert all("secret" not in (text or "") for text in texts)


def test_textarea_accepts_newlines_scrolls_to_caret_and_renders_selection() -> None:
    window = Window(width=420, height=220)
    root = Component("root")
    area = TextArea(
        "one\ntwo\nthree\nfour",
        key="notes",
        bounds=Rect(20.0, 20.0, 300.0, 76.0),
        font_size=16.0,
        padding=8.0,
    )
    root.add(area)
    mount(window, root)
    window.focus_component(area)

    assert window.scene is not None
    focused_text = "\n".join(
        node.text or "" for node in window.scene.walk() if node.key.startswith("notes:text:")
    )
    assert "four" in focused_text
    assert "one" not in focused_text

    area.select(4, 7)
    assert window.scene is not None
    selection_nodes = [
        node for node in window.scene.walk() if node.key.startswith("notes:selection:")
    ]
    assert selection_nodes

    area.select(len(area.value), len(area.value))
    _send(window, PlatformEventKind.TEXT_INPUT, text="\nfive")
    assert area.value.endswith("four\nfive")
    assert window.scene is not None
    assert any(node.text == "five" for node in window.scene.walk())

    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x26)
    assert area.caret_index < len(area.value)


def test_read_only_input_allows_focus_and_selection_but_rejects_mutation() -> None:
    window = Window(width=360, height=180)
    root = Component("root")
    field = Input(
        "locked",
        key="locked",
        bounds=Rect(20.0, 20.0, 220.0, 44.0),
        read_only=True,
    )
    root.add(field)
    mount(window, root)
    window.focus_component(field)

    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x41, ctrl=True)
    assert field.selected_text == "locked"
    _send(window, PlatformEventKind.TEXT_INPUT, text="changed")
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x08)

    assert field.value == "locked"
    assert window.focused_component is field


def test_word_jumps_follow_the_same_stops_in_both_directions():
    window = Window()
    parts = ("  ", "żółty_2", "::", "cafe\u0301  ", "❤️   ", "notes")
    field = Input("".join(parts), bounds=Rect(0, 0, 120, 36))
    mount(window, field)
    window.focus_component(field)
    field.select(0, 0)
    stops = [0]
    for part in parts:
        stops.append(stops[-1] + len(part))
    for key, expected in ((0x27, stops[1:]), (0x25, stops[-2::-1])):
        for index in expected:
            _send(window, PlatformEventKind.KEY_DOWN, key_code=key, ctrl=True)
            assert field.caret_index == index
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x25, ctrl=True)
    assert field.caret_index == 0


@pytest.mark.parametrize("control", [TextArea, CodeEditor])
def test_keyboard_extends_reverses_and_collapses_word_selection_across_lines(control):
    window = Window()
    field = control("one two\n  three", bounds=Rect(0, 0, 180, 60), read_only=True)
    mount(window, field)
    window.focus_component(field)
    field.select(4, 4)
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x27, ctrl=True, shift=True)
    assert field.selected_text == "two\n  "
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x25, ctrl=True, shift=True)
    assert not field.selected_text and field.caret_index == 4
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x24, ctrl=True, shift=True)
    assert field.selected_text == "one " and field.caret_index == 0
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x23, ctrl=True, shift=True)
    assert field.selected_text == "two\n  three"
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x25, ctrl=True)
    assert not field.selected_text and field.caret_index == 4
    assert field.value == "one two\n  three"


def test_word_selection_in_a_password_field_uses_the_visible_mask_as_one_run():
    window = Window()
    field = PasswordInput("ab c:d", bounds=Rect(0, 0, 160, 36))
    mount(window, field)
    window.focus_component(field)
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x25, ctrl=True, shift=True)
    assert (field.selection_start, field.selection_end) == (0, len(field.value))
    _send(window, PlatformEventKind.TEXT_INPUT, text="new")
    assert field.value == "new"


def test_word_shortcut_replaces_only_the_selection_and_leaves_other_modifiers_available():
    window = Window()
    field = Input("Field notes", bounds=Rect(0, 0, 200, 40))
    mount(window, field)
    window.focus_component(field)
    for modifiers in ({"ctrl": True, "alt": True}, {"ctrl": True, "meta": True}):
        arrow = PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1),
                              key_code=0x25, **modifiers)
        assert not field.emit("key_down", event=arrow).default_prevented
        assert field.caret_index == len(field.value)
    changed = []
    field.on("changed", changed.append)
    _send(window, PlatformEventKind.KEY_DOWN, key_code=0x25, ctrl=True, shift=True)
    assert field.selected_text == "notes" and not changed
    _send(window, PlatformEventKind.TEXT_INPUT, text="guide")
    assert field.value == "Field guide" and len(changed) == 1


def test_text_input_validation_and_programmatic_normalization() -> None:
    field = Input("a\nb", bounds=Rect(0.0, 0.0, 120.0, 36.0), max_length=2)
    assert field.value == "ab"

    field.value = "xyz"
    assert field.value == "xy"

    with pytest.raises(ValueError, match="max_length"):
        Input(bounds=Rect(0.0, 0.0, 120.0, 36.0), max_length=-1)
    with pytest.raises(ValueError, match="mask_character"):
        PasswordInput(bounds=Rect(0.0, 0.0, 120.0, 36.0), mask_character="\n")


def _pointer(window, kind, x, y, *, shift=False):
    window._apply_platform_event(PlatformEvent(
        kind, NativeWindowHandle(1), x=x * window.scale, y=y * window.scale,
        button=None if kind is PlatformEventKind.POINTER_MOVE else PointerButton.LEFT,
        shift=shift,
    ))


def test_drag_selects_backwards_outside_read_only_input_and_keeps_shift_anchor():
    window = Window(width=400, height=180)
    field = Input("abcdef", bounds=Rect(20, 20, 150, 44), read_only=True)
    mount(window, field)
    down, move, up = (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_MOVE,
                      PlatformEventKind.POINTER_UP)
    _pointer(window, down, 160, 40)
    assert window.pointer_capture_component is field
    _pointer(window, move, 49, 40)
    assert field.selected_text == "cdef"
    _pointer(window, up, -10, 40)
    assert field.selected_text == "abcdef" and field.caret_index == 0
    assert window.pointer_capture_component is None
    _pointer(window, move, 140, 40)
    assert field.caret_index == 0
    _pointer(window, down, 49, 40, shift=True)
    _pointer(window, up, 58, 40)
    assert field.selected_text == "def" and field.value == "abcdef"


def test_multiline_drag_ends_on_capture_loss_and_unmount():
    window = Window(width=400, height=180)
    root = Component("root")
    area = TextArea("one\ntwo\nthree", bounds=Rect(20, 20, 220, 120))
    root.add(area)
    mount(window, root)
    _pointer(window, PlatformEventKind.POINTER_DOWN, 39, 32)
    _pointer(window, PlatformEventKind.POINTER_MOVE, 49, 73)
    assert area.selected_text == "ne\ntwo\nth"
    window.release_pointer_capture()
    _pointer(window, PlatformEventKind.POINTER_MOVE, 90, 32)
    assert area.selected_text == "ne\ntwo\nth"
    _pointer(window, PlatformEventKind.POINTER_DOWN, 39, 32)
    root.remove(area)
    assert window.pointer_capture_component is None
