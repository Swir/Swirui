from swirui import Component, RangeSlider, Slider, Window, build_accessibility_tree, mount
from swirui.core import AccessibilityRole, Event
from swirui.platforms import (
    NativeWindowHandle,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)
from swirui.rendering import Point, Rect, Scene, SceneNode
from swirui.widgets import compile_component_scene


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def _pointer(window: Window, kind: PlatformEventKind, *, x: float, y: float) -> None:
    window._apply_platform_event(
        PlatformEvent(
            kind,
            NativeWindowHandle(1),
            x=x,
            y=y,
            button=PointerButton.LEFT,
        )
    )


def _key(window: Window, key_code: int) -> None:
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.KEY_DOWN,
            NativeWindowHandle(1),
            key_code=key_code,
        )
    )


def test_slider_compiles_visuals_and_numeric_accessibility() -> None:
    root = Component("root")
    slider = Slider(
        key="volume",
        bounds=Rect(20.0, 30.0, 300.0, 44.0),
        value=35.0,
        accessible_name="Volume",
    )
    root.add(slider)

    scene = compile_component_scene(root, width=400.0, height=160.0)
    tree = build_accessibility_tree(root)

    assert scene is not None
    assert scene.hit_test(Point(100.0, 50.0)) is not None
    assert _node(scene, "volume:track").hit_testable is False
    assert _node(scene, "volume:fill").bounds.width > 0.0
    assert _node(scene, "volume:thumb").bounds.width == slider.thumb_size
    assert tree is not None
    semantics = tree.find("volume")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.SLIDER
    assert semantics.name == "Volume"
    assert semantics.value == 35.0
    assert semantics.min_value == 0.0
    assert semantics.max_value == 100.0
    assert semantics.value_text == "35"


def test_slider_pointer_and_keyboard_update_value_and_rebuild_scene() -> None:
    window = Window(width=420, height=180)
    root = Component("root")
    slider = Slider(
        key="gain",
        bounds=Rect(20.0, 20.0, 300.0, 44.0),
        value=0.0,
        step=5.0,
    )
    root.add(slider)
    runtime = mount(window, root)
    changes: list[Event] = []
    slider.on("changed", changes.append)
    initial_generation = runtime.generation

    _pointer(window, PlatformEventKind.POINTER_DOWN, x=170.0, y=42.0)
    _pointer(window, PlatformEventKind.POINTER_UP, x=170.0, y=42.0)

    assert window.focused_component is slider
    assert slider.value == 50.0
    assert changes
    assert runtime.generation > initial_generation

    _key(window, 0x27)
    assert slider.value == 55.0
    _key(window, 0x24)
    assert slider.value == 0.0
    _key(window, 0x23)
    assert slider.value == 100.0
    assert window.scene is not None
    assert _node(window.scene, "gain:thumb")


def test_range_slider_selects_nearest_thumb_and_preserves_order() -> None:
    window = Window(width=460, height=200)
    root = Component("root")
    slider = RangeSlider(
        key="range",
        bounds=Rect(20.0, 20.0, 320.0, 44.0),
        lower_value=20.0,
        upper_value=80.0,
        step=5.0,
        accessible_name="Allowed range",
    )
    root.add(slider)
    mount(window, root)

    _pointer(window, PlatformEventKind.POINTER_DOWN, x=300.0, y=42.0)
    _pointer(window, PlatformEventKind.POINTER_UP, x=300.0, y=42.0)

    assert window.focused_component is slider
    assert slider.active_thumb == "upper"
    assert slider.upper_value == 90.0
    assert slider.lower_value == 20.0

    slider.lower_value = 95.0
    assert slider.lower_value == 90.0
    assert slider.upper_value == 90.0
    assert slider.active_thumb == "lower"
    _key(window, 0x25)
    assert slider.lower_value == 85.0

    tree = build_accessibility_tree(root, focused=slider)
    assert tree is not None
    semantics = tree.find("range")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.SLIDER
    assert semantics.value is None
    assert semantics.min_value == 0.0
    assert semantics.max_value == 100.0
    assert semantics.value_text == "85–90"
    assert semantics.focused is True


def test_slider_validates_range_and_finite_values() -> None:
    for kwargs in (
        {"minimum": 10.0, "maximum": 10.0},
        {"minimum": 0.0, "maximum": 10.0, "step": 0.0},
        {"minimum": float("nan"), "maximum": 10.0},
    ):
        try:
            Slider(bounds=Rect(0.0, 0.0, 100.0, 30.0), **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid slider range must raise ValueError")

    slider = RangeSlider(
        bounds=Rect(0.0, 0.0, 100.0, 30.0),
        lower_value=25.0,
        upper_value=75.0,
    )
    try:
        slider.lower_value = float("inf")
    except ValueError:
        pass
    else:
        raise AssertionError("non-finite range value must raise ValueError")


def test_range_slider_rejects_reversed_initial_interval() -> None:
    try:
        RangeSlider(
            bounds=Rect(0.0, 0.0, 100.0, 30.0),
            lower_value=80.0,
            upper_value=20.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("reversed range must raise ValueError")
