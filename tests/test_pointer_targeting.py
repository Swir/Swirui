from swirui import App, Window
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Color, NullRenderer, Rect, Scene, SceneNode, SceneNodeKind


def _scene() -> tuple[Scene, SceneNode, SceneNode]:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 640, 400))
    back = SceneNode(
        "back",
        SceneNodeKind.RECTANGLE,
        Rect(40, 40, 220, 160),
        fill=Color.from_hex("#102038"),
        z_index=1,
    )
    front = SceneNode(
        "front",
        SceneNodeKind.RECTANGLE,
        Rect(80, 70, 220, 160),
        fill=Color.from_hex("#00A8FF"),
        z_index=5,
    )
    root.add(back, front)
    return Scene(640, 400, root), back, front


def test_pointer_down_contains_topmost_target_and_scene_path() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=640, height=400)
    scene, _back, front = _scene()
    window.set_scene(scene)
    app.add_window(window)
    app.start()

    received = []
    window.on("pointer_down", received.append)
    assert window.native_handle is not None
    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            window.native_handle,
            x=100,
            y=100,
            button=PointerButton.LEFT,
        )
    )

    assert app.process_events() == 1
    assert len(received) == 1
    assert received[0].data["target"] is front
    assert [node.key for node in received[0].data["path"]] == ["root", "front"]

    app.stop()


def test_pointer_move_emits_enter_and_leave_when_hover_target_changes() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=640, height=400)
    scene, back, front = _scene()
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    entered: list[str] = []
    left: list[str] = []
    window.on("pointer_enter", lambda event: entered.append(event.data["target"].key))
    window.on("pointer_leave", lambda event: left.append(event.data["target"].key))

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_MOVE,
            window.native_handle,
            x=100,
            y=100,
        )
    )
    app.process_events()
    assert window.hovered_scene_node is front

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_MOVE,
            window.native_handle,
            x=55,
            y=55,
        )
    )
    app.process_events()
    assert window.hovered_scene_node is back

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_MOVE,
            window.native_handle,
            x=600,
            y=350,
        )
    )
    app.process_events()
    assert window.hovered_scene_node is None

    assert entered == ["front", "back"]
    assert left == ["front", "back"]

    app.stop()
