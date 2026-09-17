import pytest

from swirui import Button, Component, ScrollView, Window, build_accessibility_tree, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Point, Rect, Scene, SceneNode
from swirui.widgets import compile_component_scene


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def test_scroll_view_translates_clips_and_preserves_component_geometry() -> None:
    root = Component("root")
    scroll = ScrollView(
        key="scroll",
        bounds=Rect(100.0, 50.0, 200.0, 120.0),
        content_width=360.0,
        content_height=320.0,
        scroll_y=140.0,
        accessible_name="Results",
    )
    item = Button(
        "Visible after scroll",
        key="item",
        bounds=Rect(20.0, 180.0, 140.0, 40.0),
    )
    scroll.add(item)
    root.add(scroll)

    scene = compile_component_scene(root, width=480.0, height=320.0)

    assert scene is not None
    viewport = _node(scene, "scroll")
    item_node = _node(scene, "item")
    assert viewport.clip_to_bounds is True
    assert viewport.bounds == Rect(100.0, 50.0, 200.0, 120.0)
    assert item.bounds == Rect(20.0, 180.0, 140.0, 40.0)
    assert item_node.bounds == Rect(120.0, 90.0, 140.0, 40.0)
    assert scene.hit_test(Point(140.0, 105.0)) is item_node
    assert scene.hit_test(Point(140.0, 230.0)) is None
    assert scroll.max_scroll_y == 200.0


def test_scroll_view_auto_measures_children_and_clamps_programmatic_offsets() -> None:
    root = Component("root")
    scroll = ScrollView(
        key="scroll",
        bounds=Rect(20.0, 20.0, 180.0, 100.0),
    )
    item = Button(
        "Deep",
        key="deep",
        bounds=Rect(12.0, 250.0, 120.0, 40.0),
    )
    scroll.add(item)
    root.add(scroll)

    first = compile_component_scene(root, width=320.0, height=240.0)

    assert first is not None
    assert scroll.content_height == 290.0
    assert scroll.max_scroll_y == 190.0
    assert scroll.scroll_to(y=999.0) is True
    assert scroll.scroll_y == 190.0
    assert scroll.scroll_by(dy=50.0) is False

    second = compile_component_scene(root, width=320.0, height=240.0)

    assert second is not None
    assert _node(second, "deep").bounds == Rect(32.0, 80.0, 120.0, 40.0)


def test_scroll_view_routes_scrolled_pointer_targets_to_original_child_component() -> None:
    window = Window(width=480, height=320)
    root = Component("root")
    scroll = ScrollView(
        key="scroll",
        bounds=Rect(100.0, 50.0, 200.0, 120.0),
        content_height=320.0,
        scroll_y=140.0,
    )
    item = Button(
        "Action",
        key="action",
        bounds=Rect(20.0, 180.0, 140.0, 40.0),
    )
    scroll.add(item)
    root.add(scroll)
    runtime = mount(window, root)
    clicks = []
    item.on("click", clicks.append)
    handle = NativeWindowHandle(1)

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=140.0,
            y=105.0,
            button=PointerButton.LEFT,
        )
    )
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=140.0,
            y=105.0,
            button=PointerButton.LEFT,
        )
    )

    assert window.focused_component is item
    assert len(clicks) == 1
    assert runtime.mounted is True


def test_scroll_view_keyboard_navigation_rebuilds_scene_and_exposes_semantics() -> None:
    window = Window(width=420, height=280)
    root = Component("root")
    scroll = ScrollView(
        key="scroll",
        bounds=Rect(40.0, 40.0, 240.0, 120.0),
        content_width=360.0,
        content_height=520.0,
        accessible_name="Scrollable results",
    )
    root.add(scroll)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)
    initial_generation = runtime.generation

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=260.0,
            y=70.0,
            button=PointerButton.LEFT,
        )
    )
    assert window.focused_component is scroll

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x22)
    )

    assert scroll.scroll_y == 96.0
    assert runtime.generation == initial_generation + 1
    tree = build_accessibility_tree(root, focused=window.focused_component)
    assert tree is not None
    semantic = tree.find("scroll")
    assert semantic is not None
    assert semantic.focusable is True
    assert semantic.focused is True
    assert semantic.value == 96.0
    assert semantic.min_value == 0.0
    assert semantic.max_value == 400.0
    assert semantic.value_text == "vertical 96 of 400 DIPs; horizontal 0 of 120 DIPs"

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x23)
    )
    assert scroll.scroll_x == 120.0
    assert scroll.scroll_y == 400.0

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x24)
    )
    assert (scroll.scroll_x, scroll.scroll_y) == (0.0, 0.0)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_scroll_view_rejects_non_finite_scroll_values(value: float) -> None:
    scroll = ScrollView(bounds=Rect(0.0, 0.0, 100.0, 100.0), content_height=200.0)

    with pytest.raises(ValueError, match="scroll_y must be finite"):
        scroll.scroll_to(y=value)
