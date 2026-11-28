import pytest

from swirui import (
    Button,
    Component,
    Modal,
    RangeSlider,
    Slider,
    Window,
    build_accessibility_tree,
    mount,
)
from swirui.core import AccessibilityRole, Event
from swirui.platforms import (
    NativeWindowHandle,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)
from swirui.rendering import Color, LinearGradient, Point, Rect, Scene, SceneNode
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


def _key(window: Window, key_code: int, *, shift: bool = False) -> None:
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.KEY_DOWN,
            NativeWindowHandle(1),
            key_code=key_code,
            shift=shift,
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


@pytest.mark.parametrize("direction", [-1, 1])
def test_drag_reopens_coincident_handles_without_jumping_or_switching_ends(direction):
    window = Window(width=360, height=120)
    slider = RangeSlider(bounds=Rect(20, 20, 218, 40), lower_value=50, upper_value=50, step=5)
    mount(window, slider)
    # Start with the handle that cannot move in the requested direction.
    if direction < 0:
        slider.upper_value = 50
    changes = []
    slider.on("changed", lambda event: changes.append(event.data["active_thumb"]))
    # The shared center is x=129. Grab the opposite edge of the painted handle.
    grab = 129 - direction * 8
    _pointer(window, PlatformEventKind.POINTER_DOWN, x=grab, y=40)
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=grab - direction * 2, y=40)
    assert (slider.lower_value, slider.upper_value) == (50, 50) and not changes
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=grab + direction * 40, y=40)
    thumb = "upper" if direction > 0 else "lower"
    assert (slider.lower_value, slider.upper_value) == ((50, 70) if direction > 0 else (30, 50))
    assert slider.active_thumb == thumb and changes == [thumb]
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=grab - direction * 80, y=40)
    assert (slider.lower_value, slider.upper_value) == (50, 50)
    _pointer(window, PlatformEventKind.POINTER_UP, x=grab - direction * 90, y=40)
    assert changes == [thumb, thumb] and window.pointer_capture_component is None

    # A fresh drag can open the other side, including with no intervening move event.
    _pointer(window, PlatformEventKind.POINTER_DOWN, x=129, y=40)
    _pointer(window, PlatformEventKind.POINTER_UP, x=129 - direction * 40, y=40)
    assert (slider.lower_value, slider.upper_value) == ((30, 50) if direction > 0 else (50, 70))


def test_track_click_opens_a_collapsed_range_to_the_exact_non_step_maximum():
    window = Window(width=360, height=120)
    slider = RangeSlider(bounds=Rect(20, 20, 218, 40), maximum=10, step=3,
                         lower_value=6, upper_value=6)
    mount(window, slider)
    _pointer(window, PlatformEventKind.POINTER_DOWN, x=229, y=40)
    _pointer(window, PlatformEventKind.POINTER_UP, x=229, y=40)
    assert (slider.lower_value, slider.upper_value) == (6, 10)
    assert slider.active_thumb == "upper"


@pytest.mark.parametrize("in_dialog", [False, True])
def test_tab_visits_both_range_ends_in_each_direction(in_dialog):
    window = Window(width=420, height=240)
    controls = Component("controls")
    before = Button("Before", bounds=Rect(16, 10, 100, 32))
    slider = RangeSlider(bounds=Rect(16, 56, 280, 44), lower_value=40, upper_value=40)
    after = Button("After", bounds=Rect(16, 120, 100, 32))
    controls.add(before, slider, after)
    root = (Modal(bounds=Rect(0, 0, 420, 240), dialog_bounds=Rect(12, 12, 380, 200),
                  content=controls) if in_dialog else controls)
    mount(window, root)
    changes = []
    slider.on("changed", changes.append)
    window.focus_component(before)
    _key(window, 0x09)
    assert window.focused_component is slider and slider.active_thumb == "lower"
    _key(window, 0x09)
    assert window.focused_component is slider and slider.active_thumb == "upper"
    assert (slider.lower_value, slider.upper_value) == (40, 40) and not changes
    tree = build_accessibility_tree(slider, focused=slider)
    lower, upper = tree.children
    assert lower.name == "Lower limit" and upper.name == "Upper limit"
    assert not lower.focused and upper.focused and upper.active
    assert (lower.min_value, lower.value, lower.max_value) == (0, 40, 40)
    assert (upper.min_value, upper.value, upper.max_value) == (40, 40, 100)
    _key(window, 0x27)
    assert (slider.lower_value, slider.upper_value) == (40, 41)
    _key(window, 0x09)
    assert window.focused_component is after
    _key(window, 0x09, shift=True)
    assert window.focused_component is slider and slider.active_thumb == "upper"
    _key(window, 0x09, shift=True)
    assert window.focused_component is slider and slider.active_thumb == "lower"
    _key(window, 0x25)
    assert (slider.lower_value, slider.upper_value) == (39, 41) and len(changes) == 2
    _key(window, 0x09, shift=True)
    assert window.focused_component is before


def test_sole_range_wraps_to_the_other_end_and_skips_disabled_controls():
    root = Component()
    slider = RangeSlider(bounds=Rect(10, 10, 190, 35))
    disabled = Slider(bounds=Rect(10, 70, 190, 35))
    disabled.enabled = False
    root.add(slider, disabled)
    window = Window()
    mount(window, root)
    for reverse, expected in ((True, "upper"), (True, "lower"), (True, "upper"),
                              (False, "lower"), (False, "upper")):
        assert window.focus_next(reverse=reverse) is slider
        assert slider.active_thumb == expected


@pytest.mark.parametrize("range_control", [False, True])
def test_gradient_fill_stays_anchored_and_transparent_to_input(range_control):
    gradient = LinearGradient.two_color(Color.from_hex("#B997FF"), Color.from_hex("#8FF1BE"))
    bounds = Rect(10, 20, 218, 40)
    slider = (RangeSlider(bounds=bounds, lower_value=20, upper_value=80, fill_gradient=gradient)
              if range_control else Slider(bounds=bounds, value=80, fill_gradient=gradient))
    window = Window(width=260, height=90)
    mount(window, slider)
    track = Rect(19, 37, 200, 6)
    fill_key = f"{slider.key}:fill"
    fill = _node(window.scene, fill_key)
    expected = Rect(59, 37, 120, 6) if range_control else Rect(19, 37, 160, 6)
    assert fill.clip_to_bounds and fill.bounds == expected
    assert all(band.bounds == track for band in fill.children)
    assert not any(node.hit_testable for node in fill.walk())
    assert window.scene.hit_test(Point(119, 40)).key == slider.key

    if range_control:
        slider.lower_value = 35
        slider.upper_value = 65
    else:
        slider.value = 65
    narrower = _node(window.scene, fill_key)
    assert narrower.bounds == (Rect(89, 37, 60, 6) if range_control else Rect(19, 37, 130, 6))
    assert narrower.children[0].path is fill.children[0].path
    assert [b.fill for b in narrower.children] == [b.fill for b in fill.children]
    slider.fill_gradient = LinearGradient.two_color(
        Color.from_hex("#F00B64"), Color.from_hex("#FFDA45")
    )
    alternate = _node(window.scene, fill_key)
    assert alternate.bounds == narrower.bounds
    assert alternate.children[0].fill != fill.children[0].fill
    slider.enabled = False
    assert _node(window.scene, fill_key).fill == _node(window.scene, f"{slider.key}:track").fill
    slider.enabled = True
    slider.fill_gradient = None
    assert not _node(window.scene, fill_key).children
    with pytest.raises(TypeError, match="fill_gradient"):
        slider.fill_gradient = "mint"
    slider.fill_gradient = gradient
    slider.bounds = Rect(10, 20, 8, 40)
    assert all(node.key != fill_key for node in window.scene.walk())
    slider.bounds = bounds
    assert _node(window.scene, fill_key).bounds == narrower.bounds
    if range_control:
        slider.lower_value = slider.upper_value
    else:
        slider.value = slider.minimum
    assert all(node.key != fill_key for node in window.scene.walk())


@pytest.mark.parametrize("control", ["single", "lower", "upper"])
def test_step_keys_visit_the_short_final_interval_in_both_directions(control):
    bounds = Rect(10, 15, 218, 44)
    if control == "single":
        slider = Slider(bounds=bounds, maximum=100, step=9, value=100)
        attr = "value"
    else:
        slider = RangeSlider(bounds=bounds, maximum=100, step=9,
                             lower_value=100 if control == "lower" else 0, upper_value=100)
        attr = f"{control}_value"
        setattr(slider, attr, 100)
    window = Window()
    mount(window, slider)
    window.focus_component(slider)
    changes = []
    slider.on("changed", lambda _: changes.append(getattr(slider, attr)))
    assert getattr(slider, attr) == 100
    for key, expected in ((0x25, 99), (0x27, 100), (0x27, 100), (0x22, 18),
                          (0x21, 100), (0x24, 0), (0x23, 100)):
        _key(window, key)
        assert getattr(slider, attr) == expected
    assert changes == [99, 100, 18, 100, 0, 100]
    setattr(slider, attr, 99.4)
    assert getattr(slider, attr) == 99
    setattr(slider, attr, 99.6)
    assert getattr(slider, attr) == 100


@pytest.mark.parametrize("minimum,maximum,step,stops", [
    (-.25, .5, .3, [-.25, .05, .35, .5]),
    (0, .07, .01, [0, .01, .02, .03, .04, .05, .06, .07]),
    (0, 2.1, .7, [0, .7, 1.4, 2.1]),
    (10, 12, 50, [10, 12]),
])
def test_decimal_and_oversized_steps_visit_each_stop_once(minimum, maximum, step, stops):
    slider = Slider(bounds=Rect(10, 15, 218, 44), minimum=minimum, maximum=maximum,
                    step=step, value=minimum)
    window = Window()
    mount(window, slider)
    window.focus_component(slider)
    for key, values in ((0x26, stops[1:]), (0x28, stops[-2::-1])):
        for expected in values:
            _key(window, key)
            assert slider.value == slider.accessible_value == expected


@pytest.mark.parametrize("range_control", [False, True])
def test_pointer_uses_the_nearest_side_of_the_final_short_step(range_control):
    bounds = Rect(10, 15, 218, 44)
    slider = (RangeSlider(bounds=bounds, maximum=10, step=3, lower_value=0, upper_value=9)
              if range_control else Slider(bounds=bounds, maximum=10, step=3, value=9))
    window = Window()
    mount(window, slider)
    # Track x=19..219. The final half-step boundary (9.5) is at x=209.
    _pointer(window, PlatformEventKind.POINTER_DOWN, x=199, y=37)
    for x, expected in ((208, 9), (210, 10), (208, 9)):
        _pointer(window, PlatformEventKind.POINTER_MOVE, x=x, y=37)
        assert (slider.upper_value if range_control else slider.value) == expected
    _pointer(window, PlatformEventKind.POINTER_UP, x=210, y=37)
    assert (slider.upper_value if range_control else slider.value) == 10
    assert window.pointer_capture_component is None


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


@pytest.mark.parametrize("kind", ["single", "range"])
def test_drag_stays_with_slider_outside_track_and_releases_on_button_up(kind):
    bounds = Rect(20, 20, 220, 36)
    window = Window(width=400, height=180)
    slider = (Slider(bounds=bounds, maximum=10, step=3) if kind == "single" else
              RangeSlider(bounds=bounds, maximum=10, step=3, lower_value=3, upper_value=6))
    other = Slider(bounds=Rect(20, 90, 220, 36))
    root = Component("root")
    root.add(slider, other)
    mount(window, root)
    values = []
    slider.on("changed", lambda _: values.append(
        slider.value if isinstance(slider, Slider) else slider.upper_value))
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=150, y=38)
    _pointer(window, PlatformEventKind.POINTER_DOWN, x=150, y=38)
    assert window.pointer_capture_component is slider
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=90, y=105)
    assert values[-1] == 3 and other.value == 0
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=-25, y=105)
    assert values[-1] == (3 if kind == "range" else 0)
    _pointer(window, PlatformEventKind.POINTER_UP, x=470, y=-15)
    assert values[-1] == 10 and window.pointer_capture_component is None
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=30, y=38)
    assert values[-1] == 10
    if isinstance(slider, RangeSlider):
        assert slider.lower_value == 3 and slider.active_thumb == "upper"


@pytest.mark.parametrize("cancel", ["disable", "hide", "unmount", "release", "focus"])
def test_cancelled_slider_drag_never_resumes_on_hover(cancel):
    window = Window(width=400, height=180)
    root = Component("root")
    slider = Slider(bounds=Rect(20, 20, 220, 36))
    root.add(slider)
    mount(window, root)
    _pointer(window, PlatformEventKind.POINTER_DOWN, x=130, y=38)
    assert window.pointer_capture_component is slider and slider.value == 50
    if cancel == "disable":
        slider.enabled = False
        slider.enabled = True
    elif cancel == "hide":
        slider.visible = False
        slider.visible = True
    elif cancel == "unmount":
        root.remove(slider)
        root.add(slider)
    elif cancel == "release":
        window.release_pointer_capture(slider)
    else:
        window.focus_component(None)
    assert window.pointer_capture_component is None
    _pointer(window, PlatformEventKind.POINTER_MOVE, x=200, y=38)
    assert slider.value == 50
