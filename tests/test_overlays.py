import pytest

from swirui import (
    AccessibilityRole,
    Button,
    Component,
    Dialog,
    Modal,
    Notification,
    Toast,
    Window,
    build_accessibility_tree,
    mount,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Point, Rect, Scene, SceneNode, SceneNodeKind
from swirui.widgets import compile_component_scene


def _node(scene: Scene, key: str, *, kind: SceneNodeKind | None = None) -> SceneNode:
    return next(
        node
        for node in scene.walk()
        if node.key == key and (kind is None or node.kind is kind)
    )


def test_modal_translates_local_content_and_blocks_background_hit_testing() -> None:
    root = Component("root")
    background = Button("Background", key="background", bounds=Rect(20.0, 20.0, 160.0, 48.0))
    content = Button("Confirm", key="confirm", bounds=Rect(24.0, 28.0, 140.0, 44.0))
    modal = Modal(
        key="modal",
        bounds=Rect(0.0, 0.0, 640.0, 420.0),
        dialog_bounds=Rect(160.0, 90.0, 320.0, 220.0),
        content=content,
        accessible_name="Delete item",
    )
    root.add(background, modal)

    scene = compile_component_scene(root, width=640.0, height=420.0)

    assert scene is not None
    backdrop = _node(scene, "modal", kind=SceneNodeKind.RECTANGLE)
    confirm = _node(scene, "confirm")
    assert backdrop.bounds == Rect(0.0, 0.0, 640.0, 420.0)
    assert confirm.bounds == Rect(184.0, 118.0, 140.0, 44.0)
    assert content.bounds == Rect(24.0, 28.0, 140.0, 44.0)
    assert scene.hit_test(Point(40.0, 40.0)) is backdrop
    assert scene.hit_test(Point(200.0, 130.0)) is confirm


def test_modal_dismisses_from_backdrop_and_escape_bubbling() -> None:
    window = Window(width=640, height=420)
    root = Component("root")
    content = Button("Keep focus", key="dialog-action", bounds=Rect(24.0, 24.0, 160.0, 44.0))
    modal = Dialog(
        key="dialog",
        bounds=Rect(0.0, 0.0, 640.0, 420.0),
        dialog_bounds=Rect(160.0, 90.0, 320.0, 220.0),
        content=content,
    )
    root.add(modal)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)
    reasons: list[str] = []
    modal.on("dismissed", lambda event: reasons.append(event.data["reason"]))

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
    assert reasons == ["backdrop"]
    assert runtime.generation > 1

    assert modal.show(reason="test") is True
    window.focus_component(content)
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x1B)
    )
    assert modal.is_open is False
    assert reasons == ["backdrop", "escape"]


def test_modal_accessibility_and_configuration_validation() -> None:
    root = Component("root")
    modal = Modal(
        key="modal",
        bounds=Rect(0.0, 0.0, 500.0, 300.0),
        dialog_bounds=Rect(100.0, 60.0, 300.0, 180.0),
        accessible_name="Preferences",
    )
    root.add(modal)
    tree = build_accessibility_tree(root)

    assert tree is not None
    semantic = tree.find("modal")
    assert semantic is not None
    assert semantic.role is AccessibilityRole.DIALOG
    assert semantic.name == "Preferences"
    assert semantic.focusable is True

    with pytest.raises(ValueError, match="contained"):
        Modal(
            bounds=Rect(0.0, 0.0, 200.0, 120.0),
            dialog_bounds=Rect(150.0, 20.0, 100.0, 80.0),
        )


def test_toast_renders_gpu_text_and_expires_deterministically() -> None:
    root = Component("root")
    toast = Toast(
        "Settings were saved successfully.",
        key="toast",
        title="Saved",
        kind="success",
        duration_seconds=3.0,
        bounds=Rect(280.0, 24.0, 320.0, 92.0),
    )
    root.add(toast)
    scene = compile_component_scene(root, width=640.0, height=360.0)

    assert scene is not None
    surface = _node(scene, "toast", kind=SceneNodeKind.RECTANGLE)
    title = _node(scene, "toast:title", kind=SceneNodeKind.TEXT)
    message = _node(scene, "toast:message", kind=SceneNodeKind.TEXT)
    assert surface.hit_testable is True
    assert title.text == "Saved"
    assert message.text == "Settings were saved successfully."
    assert toast.advance(2.5) is False
    assert toast.visible is True
    assert toast.advance(0.5) is True
    assert toast.visible is False
    assert toast.elapsed_seconds == pytest.approx(3.0)


def test_toast_click_dismissal_accessibility_and_notification_alias() -> None:
    window = Window(width=640, height=360)
    root = Component("root")
    toast = Notification(
        "Connection restored.",
        key="notification",
        title="Online",
        bounds=Rect(280.0, 24.0, 320.0, 92.0),
    )
    root.add(toast)
    mount(window, root)
    handle = NativeWindowHandle(1)
    reasons: list[str] = []
    toast.on("dismissed", lambda event: reasons.append(event.data["reason"]))

    tree = build_accessibility_tree(root)
    assert tree is not None
    semantic = tree.find("notification")
    assert semantic is not None
    assert semantic.role is AccessibilityRole.ALERT
    assert semantic.name == "Online"
    assert semantic.description == "Connection restored."

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=320.0,
            y=60.0,
            button=PointerButton.LEFT,
        )
    )
    assert toast.visible is False
    assert reasons == ["click"]

    with pytest.raises(ValueError, match="kind must be one of"):
        Toast("Bad", bounds=Rect(0.0, 0.0, 240.0, 80.0), kind="purple")
    with pytest.raises(ValueError, match="duration_seconds"):
        Toast("Bad", bounds=Rect(0.0, 0.0, 240.0, 80.0), duration_seconds=0.0)
