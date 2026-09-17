import pytest

from swirui import (
    Button,
    Component,
    SplitView,
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


def test_split_view_translates_local_panes_and_clips_them() -> None:
    root = Component("root")
    first = Button(
        "First",
        key="first-action",
        bounds=Rect(12.0, 16.0, 120.0, 38.0),
    )
    second = Button(
        "Second",
        key="second-action",
        bounds=Rect(14.0, 18.0, 130.0, 38.0),
    )
    split = SplitView(
        key="split",
        bounds=Rect(40.0, 30.0, 400.0, 180.0),
        first=first,
        second=second,
        split_ratio=0.4,
        divider_size=10.0,
    )
    root.add(split)

    scene = compile_component_scene(root, width=520.0, height=300.0)

    assert scene is not None
    first_pane = _node(scene, "split:pane:first")
    second_pane = _node(scene, "split:pane:second")
    divider = _node(scene, "split", kind=SceneNodeKind.RECTANGLE)
    first_node = _node(scene, "first-action")
    second_node = _node(scene, "second-action")
    assert split.first_pane_bounds == Rect(40.0, 30.0, 156.0, 180.0)
    assert divider.bounds == Rect(196.0, 30.0, 10.0, 180.0)
    assert split.second_pane_bounds == Rect(206.0, 30.0, 234.0, 180.0)
    assert first_pane.clip_to_bounds is True
    assert second_pane.clip_to_bounds is True
    assert first.bounds == Rect(12.0, 16.0, 120.0, 38.0)
    assert second.bounds == Rect(14.0, 18.0, 130.0, 38.0)
    assert first_node.bounds == Rect(52.0, 46.0, 120.0, 38.0)
    assert second_node.bounds == Rect(220.0, 48.0, 130.0, 38.0)
    assert scene.hit_test(Point(200.0, 80.0)) is divider
    assert scene.hit_test(Point(240.0, 60.0)) is second_node


def test_split_view_drag_continues_when_pointer_moves_over_child_pane() -> None:
    window = Window(width=560, height=320)
    root = Component("root")
    first = Button("First", key="first", bounds=Rect(12.0, 20.0, 180.0, 60.0))
    second = Button("Second", key="second", bounds=Rect(12.0, 20.0, 180.0, 60.0))
    split = SplitView(
        key="split",
        bounds=Rect(40.0, 40.0, 420.0, 180.0),
        first=first,
        second=second,
        split_ratio=0.5,
        divider_size=8.0,
    )
    root.add(split)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)
    changes: list[float] = []
    split.on("split_changed", lambda event: changes.append(event.data["ratio"]))
    divider = split.divider_bounds
    down_x = divider.x + divider.width / 2.0

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=down_x,
            y=100.0,
            button=PointerButton.LEFT,
        )
    )

    assert window.focused_component is split
    assert split.dragging is True

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_MOVE,
            handle,
            x=330.0,
            y=82.0,
            button=PointerButton.LEFT,
        )
    )

    assert split.split_ratio > 0.65
    assert changes
    assert runtime.generation > 1

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=330.0,
            y=82.0,
            button=PointerButton.LEFT,
        )
    )
    assert split.dragging is False


def test_split_view_keyboard_and_accessibility_semantics() -> None:
    window = Window(width=520, height=300)
    root = Component("root")
    split = SplitView(
        key="split",
        bounds=Rect(40.0, 40.0, 360.0, 180.0),
        first=Button("A", bounds=Rect(10.0, 10.0, 100.0, 40.0)),
        second=Button("B", bounds=Rect(10.0, 10.0, 100.0, 40.0)),
        orientation="vertical",
        split_ratio=0.5,
        min_ratio=0.2,
        max_ratio=0.8,
        keyboard_step=0.1,
        accessible_name="Editor split",
    )
    root.add(split)
    mount(window, root)
    window.focus_component(split)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x28)
    )
    assert split.split_ratio == pytest.approx(0.6)

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x23)
    )
    assert split.split_ratio == pytest.approx(0.8)

    tree = build_accessibility_tree(root, focused=window.focused_component)
    assert tree is not None
    semantic = tree.find("split")
    assert semantic is not None
    assert semantic.focusable is True
    assert semantic.focused is True
    assert semantic.value == pytest.approx(80.0)
    assert semantic.min_value == pytest.approx(20.0)
    assert semantic.max_value == pytest.approx(80.0)
    assert semantic.value_text == "80% first pane"


def test_split_view_clamps_programmatic_ratio_and_rejects_invalid_configuration() -> None:
    split = SplitView(
        bounds=Rect(0.0, 0.0, 300.0, 160.0),
        split_ratio=0.5,
        min_ratio=0.25,
        max_ratio=0.75,
    )

    assert split.set_split_ratio(0.95) is True
    assert split.split_ratio == pytest.approx(0.75)
    assert split.set_split_ratio(0.9) is False

    with pytest.raises(ValueError, match="orientation"):
        SplitView(bounds=Rect(0.0, 0.0, 100.0, 100.0), orientation="diagonal")
    with pytest.raises(ValueError, match="min_ratio"):
        SplitView(
            bounds=Rect(0.0, 0.0, 100.0, 100.0),
            min_ratio=0.9,
            max_ratio=0.4,
        )
    with pytest.raises(ValueError, match="both first and second"):
        SplitView(
            bounds=Rect(0.0, 0.0, 100.0, 100.0),
            first=Component("only"),
        )
