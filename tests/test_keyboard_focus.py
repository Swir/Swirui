from swirui import App, Component, Window
from swirui.core import Event, EventPhase
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind
from swirui.rendering import Color, Rect, Scene, SceneNode, SceneNodeKind


def _focused_app() -> tuple[App, NullPlatformBackend, Window, Component, Component, Component]:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend)
    window = Window()
    root = Component("root", key="root")
    panel = Component("panel", key="panel")
    field = Component("field", key="field", focusable=True)
    panel.add(field)
    root.add(panel)
    window.set_root(root)
    app.add_window(window)
    app.start()
    window.focus_component(field)
    return app, backend, window, root, panel, field


def test_keyboard_event_routes_capture_target_and_bubble() -> None:
    app, backend, window, root, panel, field = _focused_app()
    assert window.native_handle is not None
    calls: list[tuple[str, EventPhase]] = []

    root.on("key_down", lambda event: calls.append(("root-capture", event.phase)), capture=True)
    panel.on("key_down", lambda event: calls.append(("panel-capture", event.phase)), capture=True)
    field.on("key_down", lambda event: calls.append(("field-capture", event.phase)), capture=True)
    field.on("key_down", lambda event: calls.append(("field", event.phase)))
    panel.on("key_down", lambda event: calls.append(("panel", event.phase)))
    root.on("key_down", lambda event: calls.append(("root", event.phase)))

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.KEY_DOWN,
            window.native_handle,
            key_code=65,
        )
    )
    app.process_events()

    assert calls == [
        ("root-capture", EventPhase.CAPTURE),
        ("panel-capture", EventPhase.CAPTURE),
        ("field-capture", EventPhase.TARGET),
        ("field", EventPhase.TARGET),
        ("panel", EventPhase.BUBBLE),
        ("root", EventPhase.BUBBLE),
    ]
    app.stop()


def test_text_input_routes_only_to_focused_branch() -> None:
    app, backend, window, root, _panel, field = _focused_app()
    assert window.native_handle is not None
    other = Component("other", key="other", focusable=True)
    root.add(other)
    seen: list[tuple[str, str | None]] = []

    field.on(
        "text_input",
        lambda event: seen.append(("field", event.data["event"].text)),
    )
    other.on(
        "text_input",
        lambda event: seen.append(("other", event.data["event"].text)),
    )

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.TEXT_INPUT,
            window.native_handle,
            text="ą",
        )
    )
    app.process_events()

    assert seen == [("field", "ą")]
    app.stop()


def test_keyboard_capture_can_stop_propagation_before_target() -> None:
    app, backend, window, root, _panel, field = _focused_app()
    assert window.native_handle is not None
    calls: list[str] = []

    def stop_at_root(event: Event) -> None:
        calls.append("root")
        event.stop_propagation()

    root.on("key_up", stop_at_root, capture=True)
    field.on("key_up", lambda _event: calls.append("field"))

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.KEY_UP,
            window.native_handle,
            key_code=13,
        )
    )
    app.process_events()

    assert calls == ["root"]
    app.stop()


def test_pointer_down_focuses_focusable_scene_target() -> None:
    backend = NullPlatformBackend()
    app = App(platform_backend=backend)
    window = Window(width=320, height=240)
    root = Component("root", key="root")
    field = Component("field", key="field", focusable=True)
    root.add(field)
    window.set_root(root)

    scene_root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 320, 240))
    scene_root.add(
        SceneNode(
            "field",
            SceneNodeKind.RECTANGLE,
            Rect(20, 30, 180, 50),
            fill=Color.from_hex("#225588"),
        )
    )
    window.set_scene(Scene(320, 240, scene_root))
    app.add_window(window)
    app.start()
    assert window.native_handle is not None

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            window.native_handle,
            x=40.0,
            y=50.0,
        )
    )
    app.process_events()

    assert window.focused_component is field
    app.stop()


def test_component_focus_lifecycle_and_root_replacement() -> None:
    window = Window()
    root = Component("root")
    first = Component("first", focusable=True)
    second = Component("second", focusable=True)
    root.add(first, second)
    window.set_root(root)
    lifecycle: list[str] = []
    first.on("focus_gained", lambda _event: lifecycle.append("first-gained"))
    first.on("focus_lost", lambda _event: lifecycle.append("first-lost"))
    second.on("focus_gained", lambda _event: lifecycle.append("second-gained"))

    window.focus_component(first)
    window.focus_component(second)

    assert window.focused_component is second
    assert lifecycle == ["first-gained", "first-lost", "second-gained"]

    replacement = Component("replacement")
    window.set_root(replacement)
    assert window.focused_component is None


def test_focus_next_wraps_and_skips_ineligible_components() -> None:
    window = Window()
    root = Component("root")
    first = Component("first", focusable=True)
    disabled = Component("disabled", focusable=True)
    disabled.enabled = False
    hidden = Component("hidden", focusable=True)
    hidden.visible = False
    second = Component("second", focusable=True)
    root.add(first, disabled, hidden, second)
    window.set_root(root)

    assert window.focus_next() is first
    assert window.focus_next() is second
    assert window.focus_next() is first
    assert window.focus_next(reverse=True) is second


def test_focus_rejects_component_outside_root_nonfocusable_or_disabled() -> None:
    window = Window()
    root = Component("root")
    inside = Component("inside", focusable=True)
    outside = Component("outside", focusable=True)
    root.add(inside)
    window.set_root(root)

    try:
        window.focus_component(outside)
    except ValueError as exc:
        assert "root tree" in str(exc)
    else:
        raise AssertionError("focus_component accepted a component outside the root tree")

    nonfocusable = Component("nonfocusable")
    root.add(nonfocusable)
    try:
        window.focus_component(nonfocusable)
    except ValueError as exc:
        assert "focusable" in str(exc)
    else:
        raise AssertionError("focus_component accepted a non-focusable component")

    inside.enabled = False
    try:
        window.focus_component(inside)
    except ValueError as exc:
        assert "enabled and visible" in str(exc)
    else:
        raise AssertionError("focus_component accepted a disabled component")
