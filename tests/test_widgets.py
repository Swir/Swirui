import time

import pytest

from swirui import App, Button, Component, IconButton, Label, Text, Window, mount
from swirui.core import AccessibilityRole, Event
from swirui.platforms import (
    NativeWindowHandle,
    NullPlatformBackend,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)
from swirui.rendering import Color, NullRenderer, Point, Rect, Scene, SceneNode, SceneNodeKind
from swirui.widgets import WidgetRuntime, compile_component_scene


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def test_label_compiles_to_native_text_scene_and_invalidates_root() -> None:
    root = Component("root", key="root")
    label = Label(
        "Hello GPU",
        key="title",
        bounds=Rect(12.0, 16.0, 220.0, 32.0),
        font_size=22.0,
        color=Color.from_hex("#62E5FF"),
    )
    root.add(label)
    invalidations: list[Event] = []
    root.on("invalidated", invalidations.append)

    scene = compile_component_scene(root, width=640.0, height=360.0)

    assert scene is not None
    assert scene.root.kind is SceneNodeKind.GROUP
    text_node = _node(scene, "title")
    assert text_node.kind is SceneNodeKind.TEXT
    assert text_node.text == "Hello GPU"
    assert text_node.hit_testable is False
    assert label.accessibility_role is AccessibilityRole.TEXT
    assert label.accessible_name == "Hello GPU"

    label.text = "Retained text"

    assert label.accessible_name == "Retained text"
    assert invalidations[-1].data["component"] is label
    assert invalidations[-1].data["reason"] == "text"


def test_text_is_public_label_variant() -> None:
    text = Text("Status", bounds=Rect(0.0, 0.0, 120.0, 24.0))

    assert isinstance(text, Label)
    assert text.build_scene_node().kind is SceneNodeKind.TEXT


def test_button_compiles_hit_target_and_decorative_text() -> None:
    root = Component("root", key="root")
    button = Button("Launch", key="launch", bounds=Rect(20.0, 30.0, 160.0, 48.0))
    root.add(button)

    scene = compile_component_scene(root, width=320.0, height=200.0)

    assert scene is not None
    button_node = _node(scene, "launch")
    content_node = _node(scene, "launch:content")
    assert button_node.kind is SceneNodeKind.RECTANGLE
    assert button_node.hit_testable is True
    assert content_node.kind is SceneNodeKind.TEXT
    assert content_node.hit_testable is False
    assert scene.hit_test(Point(40.0, 50.0)) is button_node
    assert button.focusable is True
    assert button.accessibility_role is AccessibilityRole.BUTTON
    assert button.accessible_name == "Launch"


def test_disabled_ancestor_prunes_pointer_target_for_widget_subtree() -> None:
    root = Component("root")
    disabled_panel = Component("disabled-panel")
    disabled_panel.enabled = False
    button = Button("Blocked", bounds=Rect(20.0, 20.0, 120.0, 44.0))
    disabled_panel.add(button)
    root.add(disabled_panel)

    scene = compile_component_scene(root, width=320.0, height=200.0)

    assert scene is not None
    assert scene.hit_test(Point(30.0, 30.0)) is None
    assert _node(scene, button.key).hit_testable is False


def test_widget_runtime_rebuilds_on_retained_property_change_and_resize() -> None:
    window = Window(width=640, height=360)
    root = Component("root")
    label = Label("One", bounds=Rect(20.0, 20.0, 200.0, 32.0))
    root.add(label)
    runtime = WidgetRuntime(window).mount(root)

    first = window.scene
    assert first is not None
    assert first.generation == 1
    assert first.width == 640.0

    label.text = "Two"

    second = window.scene
    assert second is not None
    assert second is not first
    assert second.generation == 2
    assert _node(second, label.key).text == "Two"

    window.resize(720, 420)

    third = window.scene
    assert third is not None
    assert third.generation == 3
    assert (third.width, third.height) == (720.0, 420.0)

    runtime.unmount()
    assert runtime.mounted is False
    assert window.root is None
    assert window.scene is None


def test_button_pointer_and_keyboard_activation_use_routed_window_input() -> None:
    window = Window(width=400, height=240)
    root = Component("root")
    button = Button("Run", key="run", bounds=Rect(30.0, 30.0, 140.0, 48.0))
    root.add(button)
    runtime = mount(window, root)
    clicks: list[Event] = []
    button.on("click", clicks.append)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=50.0,
            y=50.0,
            button=PointerButton.LEFT,
        )
    )
    assert window.focused_component is button
    assert button.pressed is True

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=50.0,
            y=50.0,
            button=PointerButton.LEFT,
        )
    )
    assert button.pressed is False
    assert len(clicks) == 1

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x0D)
    )
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_UP, handle, key_code=0x0D)
    )
    assert len(clicks) == 2

    button.enabled = False
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=50.0,
            y=50.0,
            button=PointerButton.LEFT,
        )
    )
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=50.0,
            y=50.0,
            button=PointerButton.LEFT,
        )
    )
    assert len(clicks) == 2
    runtime.unmount()


def test_hover_identity_survives_scene_rebuilds() -> None:
    window = Window(width=400, height=240)
    root = Component("root")
    button = Button("Hover", key="hover", bounds=Rect(30.0, 30.0, 140.0, 48.0))
    root.add(button)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=50.0, y=50.0)
    )

    assert button.hovered is True
    assert window.hovered_scene_node is not None
    assert window.hovered_scene_node.key == button.key
    generation = runtime.generation

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=55.0, y=50.0)
    )

    assert runtime.generation == generation
    assert window.hovered_scene_node is not None
    assert window.hovered_scene_node.key == button.key


def test_icon_button_requires_semantic_name_and_uses_button_role() -> None:
    with pytest.raises(ValueError, match="accessible_name"):
        IconButton("★", bounds=Rect(0.0, 0.0, 44.0, 44.0), accessible_name="")

    icon = IconButton(
        "★",
        key="favorite",
        bounds=Rect(0.0, 0.0, 44.0, 44.0),
        accessible_name="Favorite",
    )

    assert icon.icon == "★"
    assert icon.accessible_name == "Favorite"
    assert icon.accessibility_role is AccessibilityRole.BUTTON
    assert icon.build_scene_node().kind is SceneNodeKind.RECTANGLE


def test_widget_runtime_scene_changes_schedule_real_app_frame() -> None:
    renderer = NullRenderer()
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=640, height=360))
    root = Component("root")
    label = Label("Initial", bounds=Rect(20.0, 20.0, 200.0, 32.0))
    root.add(label)
    runtime = mount(window, root)

    app.start()
    initial_frames = renderer.frames_rendered

    label.text = "Updated"
    rendered = app.render_pending(time.monotonic() + 1.0)

    assert rendered == 1
    assert renderer.frames_rendered == initial_frames + 1
    assert window.scene is not None
    assert _node(window.scene, label.key).text == "Updated"

    app.stop()
    assert runtime.mounted is False
