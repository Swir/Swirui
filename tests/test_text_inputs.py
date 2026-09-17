import pytest

from swirui import Component, Input, PasswordInput, TextArea, Window, mount
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
    focused_text = _node(window.scene, "notes:text")
    assert "four" in (focused_text.text or "")
    assert "one" not in (focused_text.text or "")

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
    assert "five" in (_node(window.scene, "notes:text").text or "")

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


def test_text_input_validation_and_programmatic_normalization() -> None:
    field = Input("a\nb", bounds=Rect(0.0, 0.0, 120.0, 36.0), max_length=2)
    assert field.value == "ab"

    field.value = "xyz"
    assert field.value == "xy"

    with pytest.raises(ValueError, match="max_length"):
        Input(bounds=Rect(0.0, 0.0, 120.0, 36.0), max_length=-1)
    with pytest.raises(ValueError, match="mask_character"):
        PasswordInput(bounds=Rect(0.0, 0.0, 120.0, 36.0), mask_character="\n")
