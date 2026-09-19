import math

from swirui import App, Component, Window
from swirui.core import Event, EventPhase
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Color, NullRenderer, Point, Rect, Scene, SceneNode, SceneNodeKind
from swirui.rendering.affine import Affine2D


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


def _components() -> tuple[Component, Component, Component]:
    root = Component("root", key="root")
    back = Component("back", key="back")
    front = Component("front", key="front")
    root.add(back, front)
    return root, back, front


def _pointer_down(handle: object) -> PlatformEvent:
    return PlatformEvent(
        PlatformEventKind.POINTER_DOWN,
        handle,
        x=100,
        y=100,
        button=PointerButton.LEFT,
    )


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
    backend.post_event(_pointer_down(window.native_handle))

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


def test_pointer_event_routes_capture_target_and_bubble_through_components() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=640, height=400)
    scene, _back_scene, front_scene = _scene()
    root, _back_component, front = _components()
    window.set_root(root)
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    route: list[tuple[str, EventPhase, object, object | None]] = []
    root.on(
        "pointer_down",
        lambda event: route.append(
            ("root-capture", event.phase, event.source, event.current_target)
        ),
        capture=True,
    )
    front.on(
        "pointer_down",
        lambda event: route.append(("front", event.phase, event.source, event.current_target)),
    )
    root.on(
        "pointer_down",
        lambda event: route.append(
            ("root-bubble", event.phase, event.source, event.current_target)
        ),
    )

    window_events = []
    window.on("pointer_down", window_events.append)
    backend.post_event(_pointer_down(window.native_handle))

    assert app.process_events() == 1
    assert [(name, phase) for name, phase, _source, _current in route] == [
        ("root-capture", EventPhase.CAPTURE),
        ("front", EventPhase.TARGET),
        ("root-bubble", EventPhase.BUBBLE),
    ]
    assert all(source is front for _name, _phase, source, _current in route)
    assert route[0][3] is root
    assert route[1][3] is front
    assert route[2][3] is root

    assert window_events[0].data["target"] is front_scene
    assert window_events[0].data["component_target"] is front
    assert window_events[0].data["component_path"] == (root, front)

    app.stop()


def test_rotated_ancestor_routes_pointer_to_visual_child_position() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=240, height=220)
    rotation = Affine2D.rotation(math.pi / 2.0, origin=Point(100.0, 100.0))
    scene_root = SceneNode(
        "root",
        SceneNodeKind.GROUP,
        Rect(0.0, 0.0, 220.0, 200.0),
        hit_testable=False,
        transform=rotation,
    )
    scene_child = SceneNode(
        "front",
        SceneNodeKind.RECTANGLE,
        Rect(120.0, 90.0, 40.0, 20.0),
        fill=Color.from_hex("#00A8FF"),
    )
    scene_root.add(scene_child)
    scene = Scene(240.0, 220.0, scene_root)

    root = Component("root", key="root")
    front = Component("front", key="front")
    root.add(front)
    window.set_root(root)
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    received: list[tuple[EventPhase, object]] = []
    front.on("pointer_down", lambda event: received.append((event.phase, event.source)))
    visual_target = rotation.transform_point(Point(140.0, 100.0))
    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            window.native_handle,
            x=visual_target.x,
            y=visual_target.y,
            button=PointerButton.LEFT,
        )
    )

    assert app.process_events() == 1
    assert received == [(EventPhase.TARGET, front)]
    assert scene.hit_test(visual_target) is scene_child

    app.stop()


def test_capture_handler_can_stop_component_pointer_propagation() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=640, height=400)
    scene, _back_scene, _front_scene = _scene()
    root, _back_component, front = _components()
    window.set_root(root)
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    received: list[str] = []

    def stop_at_root(event: Event) -> None:
        received.append("root-capture")
        event.stop_propagation()

    root.on("pointer_down", stop_at_root, capture=True)
    front.on("pointer_down", lambda _event: received.append("front"))
    root.on("pointer_down", lambda _event: received.append("root-bubble"))

    backend.post_event(_pointer_down(window.native_handle))
    assert app.process_events() == 1
    assert received == ["root-capture"]

    app.stop()


def test_explicit_pointer_capture_routes_move_and_up_outside_hit_target() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=640, height=400)
    scene, _back_scene, _front_scene = _scene()
    root, _back_component, front = _components()
    window.set_root(root)
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    routed: list[tuple[str, object]] = []
    window_moves: list[Event] = []

    def capture_press(event: Event) -> None:
        routed.append((event.type, event.source))
        window.capture_pointer(front)
        event.prevent_default()

    front.on("pointer_down", capture_press)
    front.on("pointer_move", lambda event: routed.append((event.type, event.source)))
    front.on("pointer_up", lambda event: routed.append((event.type, event.source)))
    window.on("pointer_move", window_moves.append)

    backend.post_event(_pointer_down(window.native_handle))
    assert app.process_events() == 1
    assert window.pointer_capture_component is front

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_MOVE,
            window.native_handle,
            x=610,
            y=360,
        )
    )
    assert app.process_events() == 1
    assert window.hovered_scene_node is None
    assert routed[-1] == ("pointer_move", front)
    assert window_moves[-1].data["target"] is None
    assert window_moves[-1].data["hit_component_target"] is None
    assert window_moves[-1].data["component_target"] is front
    assert window_moves[-1].data["pointer_captured"] is True

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            window.native_handle,
            x=610,
            y=360,
            button=PointerButton.LEFT,
        )
    )
    assert app.process_events() == 1
    assert routed[-1] == ("pointer_up", front)
    assert window.pointer_capture_component is None

    app.stop()


def test_focus_loss_releases_pointer_capture() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend, renderer=NullRenderer())
    window = Window(width=640, height=400)
    scene, _back_scene, _front_scene = _scene()
    root, _back_component, front = _components()
    window.set_root(root)
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    front.on("pointer_down", lambda _event: window.capture_pointer(front))
    backend.post_event(_pointer_down(window.native_handle))
    assert app.process_events() == 1
    assert window.pointer_capture_component is front

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.FOCUS,
            window.native_handle,
            focused=False,
        )
    )
    assert app.process_events() == 1
    assert window.pointer_capture_component is None

    app.stop()
