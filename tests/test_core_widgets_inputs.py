from swirui import (
    Checkbox,
    Component,
    Input,
    PasswordInput,
    RadioButton,
    Switch,
    TextArea,
    Window,
    mount,
)
from swirui.core import AccessibilityRole, Event
from swirui.platforms import (
    NativeWindowHandle,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)
from swirui.rendering import Rect, Scene, SceneNode


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def _keyboard(window: Window, handle: NativeWindowHandle, kind: PlatformEventKind, key: int) -> None:
    window._apply_platform_event(PlatformEvent(kind, handle, key_code=key))


def test_input_routes_text_editing_and_submit_through_window_focus() -> None:
    window = Window(width=480, height=240)
    root = Component("root")
    field = Input(
        "ab",
        key="field",
        bounds=Rect(20.0, 20.0, 220.0, 44.0),
        placeholder="Name",
        max_length=5,
    )
    root.add(field)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)
    changes: list[Event] = []
    submits: list[Event] = []
    field.on("value_changed", changes.append)
    field.on("submit", submits.append)

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

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.TEXT_INPUT, handle, text="c")
    )
    assert field.value == "abc"
    assert field.caret_index == 3

    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x25)
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.TEXT_INPUT, handle, text="Z")
    )
    assert field.value == "abZc"

    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x08)
    assert field.value == "abc"

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.TEXT_INPUT, handle, text="deFG")
    )
    assert field.value == "abdec"
    assert len(changes) >= 4

    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x0D)
    assert submits[-1].data["value"] == "abdec"

    assert window.scene is not None
    assert _node(window.scene, "field").hit_testable is True
    assert _node(window.scene, "field:caret").hit_testable is False
    runtime.unmount()


def test_password_input_masks_scene_text_until_revealed() -> None:
    field = PasswordInput(
        "hunter2",
        key="password",
        bounds=Rect(0.0, 0.0, 220.0, 44.0),
    )

    masked = field.build_scene_node()
    masked_text = next(node for node in masked.walk() if node.key == "password:text")
    assert masked_text.text == "•••••••"
    assert "hunter2" not in tuple(node.text for node in masked.walk() if node.text is not None)
    assert field.accessibility_role is AccessibilityRole.TEXT_BOX
    assert field.accessible_name == "Password"

    field.reveal = True
    revealed = field.build_scene_node()
    text = next(node for node in revealed.walk() if node.key == "password:text")
    assert text.text == "hunter2"


def test_text_area_accepts_newlines_and_uses_line_aware_home_end() -> None:
    window = Window(width=480, height=320)
    root = Component("root")
    area = TextArea(
        "one\ntwo",
        key="notes",
        bounds=Rect(20.0, 20.0, 320.0, 160.0),
        placeholder="Notes",
    )
    root.add(area)
    mount(window, root)
    window.focus_component(area)
    handle = NativeWindowHandle(1)

    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x24)
    assert area.caret_index == 4
    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x23)
    assert area.caret_index == 7
    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x0D)
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.TEXT_INPUT, handle, text="three")
    )

    assert area.value == "one\ntwo\nthree"
    assert window.scene is not None
    assert _node(window.scene, "notes:line:2").text == "three"


def test_checkbox_pointer_and_keyboard_activation_emit_boolean_state() -> None:
    window = Window(width=400, height=220)
    root = Component("root")
    checkbox = Checkbox(
        "GPU effects",
        key="effects",
        bounds=Rect(20.0, 20.0, 180.0, 32.0),
    )
    root.add(checkbox)
    mount(window, root)
    handle = NativeWindowHandle(1)
    changes: list[Event] = []
    checkbox.on("checked_changed", changes.append)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=30.0,
            y=30.0,
            button=PointerButton.LEFT,
        )
    )
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=30.0,
            y=30.0,
            button=PointerButton.LEFT,
        )
    )
    assert checkbox.checked is True
    assert window.focused_component is checkbox

    _keyboard(window, handle, PlatformEventKind.KEY_DOWN, 0x20)
    _keyboard(window, handle, PlatformEventKind.KEY_UP, 0x20)
    assert checkbox.checked is False
    assert [event.data["checked"] for event in changes] == [True, False]


def test_radio_buttons_enforce_group_exclusivity() -> None:
    root = Component("root")
    first = RadioButton(
        "First",
        group="quality",
        checked=True,
        bounds=Rect(0.0, 0.0, 140.0, 32.0),
    )
    second = RadioButton(
        "Second",
        group="quality",
        bounds=Rect(0.0, 40.0, 140.0, 32.0),
    )
    other = RadioButton(
        "Other",
        group="theme",
        checked=True,
        bounds=Rect(0.0, 80.0, 140.0, 32.0),
    )
    root.add(first, second, other)

    second.toggle()

    assert first.checked is False
    assert second.checked is True
    assert other.checked is True
    assert second.accessibility_role is AccessibilityRole.RADIO


def test_switch_compiles_thumb_position_and_disabled_hit_state() -> None:
    switch = Switch(
        key="wifi",
        bounds=Rect(10.0, 10.0, 52.0, 28.0),
        accessible_name="Wi-Fi",
    )
    off = switch.build_scene_node()
    off_thumb = next(node for node in off.walk() if node.key == "wifi:thumb")

    switch.checked = True
    on = switch.build_scene_node()
    on_thumb = next(node for node in on.walk() if node.key == "wifi:thumb")

    assert on_thumb.bounds.x > off_thumb.bounds.x
    assert switch.accessibility_role is AccessibilityRole.SWITCH

    switch.enabled = False
    assert switch.build_scene_node().hit_testable is False
