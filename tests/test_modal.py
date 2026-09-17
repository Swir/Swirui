import pytest

from swirui import (
    AccessibilityRole,
    Button,
    Component,
    Dialog,
    Modal,
    Window,
    build_accessibility_tree,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Point, Rect, Scene, SceneNode
from swirui.widgets import compile_component_scene


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def _dialog_tree(*, initially_open: bool = True) -> tuple[Component, Button, Button, Modal]:
    content = Component("dialog-content")
    accept = Button("Accept", key="accept", bounds=Rect(20.0, 24.0, 120.0, 42.0))
    cancel = Button("Cancel", key="cancel", bounds=Rect(160.0, 24.0, 120.0, 42.0))
    content.add(accept, cancel)
    modal = Modal(
        key="modal",
        bounds=Rect(0.0, 0.0, 640.0, 400.0),
        dialog_bounds=Rect(150.0, 110.0, 340.0, 170.0),
        content=content,
        initially_open=initially_open,
        accessible_name="Confirm changes",
    )
    return content, accept, cancel, modal


def test_modal_translates_dialog_local_content_and_blocks_underlay_hit_testing() -> None:
    root = Component("root")
    underlay = Button("Underlay", key="underlay", bounds=Rect(20.0, 20.0, 180.0, 50.0))
    _content, accept, _cancel, modal = _dialog_tree()
    root.add(underlay, modal)

    scene = compile_component_scene(root, width=640.0, height=400.0)

    assert scene is not None
    accept_node = _node(scene, "accept")
    assert accept.bounds == Rect(20.0, 24.0, 120.0, 42.0)
    assert accept_node.bounds == Rect(170.0, 134.0, 120.0, 42.0)
    assert _node(scene, "modal:content").clip_to_bounds is True
    assert scene.hit_test(Point(40.0, 40.0)) is _node(scene, "modal")
    assert scene.hit_test(Point(180.0, 150.0)) is accept_node


def test_modal_runtime_moves_traps_and_restores_keyboard_focus() -> None:
    window = Window(width=640, height=400)
    root = Component("root")
    background = Button("Background", key="background", bounds=Rect(20.0, 20.0, 180.0, 50.0))
    _content, accept, cancel, modal = _dialog_tree(initially_open=False)
    root.add(background, modal)
    runtime = mount(window, root)
    window.focus_component(background)
    handle = NativeWindowHandle(1)

    assert modal.show(reason="test") is True
    assert modal.is_open is True
    assert window.focused_component is accept
    generation_after_open = runtime.generation

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x09)
    )
    assert window.focused_component is cancel

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x09)
    )
    assert window.focused_component is accept

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x09, shift=True)
    )
    assert window.focused_component is cancel

    dismissed: list[str] = []
    modal.on("dismissed", lambda event: dismissed.append(event.data["reason"]))
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x1B)
    )

    assert modal.is_open is False
    assert dismissed == ["escape"]
    assert window.focused_component is background
    assert runtime.generation > generation_after_open
    assert window.scene is not None
    assert all(node.key != "modal" for node in window.scene.walk())


def test_modal_scrim_dismissal_does_not_fire_inside_dialog() -> None:
    window = Window(width=640, height=400)
    root = Component("root")
    background = Button("Background", key="background", bounds=Rect(20.0, 20.0, 180.0, 50.0))
    _content, _accept, _cancel, modal = _dialog_tree(initially_open=False)
    root.add(background, modal)
    mount(window, root)
    window.focus_component(background)
    handle = NativeWindowHandle(1)

    modal.show()
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=320.0,
            y=240.0,
            button=PointerButton.LEFT,
        )
    )
    assert modal.is_open is True

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=40.0,
            y=40.0,
            button=PointerButton.LEFT,
        )
    )
    assert modal.is_open is False
    assert window.focused_component is background


def test_modal_accessibility_and_configuration_contract() -> None:
    root = Component("root")
    _content, _accept, _cancel, modal = _dialog_tree()
    root.add(modal)

    tree = build_accessibility_tree(root)
    assert tree is not None
    semantic = tree.find("modal")
    assert semantic is not None
    assert semantic.role is AccessibilityRole.DIALOG
    assert semantic.name == "Confirm changes"

    modal.dismiss()
    hidden_tree = build_accessibility_tree(root)
    assert hidden_tree is not None
    assert hidden_tree.find("modal") is None

    dialog = Dialog(
        bounds=Rect(0.0, 0.0, 320.0, 240.0),
        dialog_bounds=Rect(60.0, 50.0, 200.0, 140.0),
    )
    assert isinstance(dialog, Modal)

    with pytest.raises(ValueError, match="fully contained"):
        Modal(
            bounds=Rect(0.0, 0.0, 320.0, 240.0),
            dialog_bounds=Rect(250.0, 180.0, 120.0, 100.0),
        )
    with pytest.raises(ValueError, match="positive dimensions"):
        Modal(
            bounds=Rect(0.0, 0.0, 320.0, 240.0),
            dialog_bounds=Rect(20.0, 20.0, 0.0, 100.0),
        )
