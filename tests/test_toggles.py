from dataclasses import replace
from types import SimpleNamespace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    AnimationController,
    App,
    Checkbox,
    Component,
    RadioButton,
    Switch,
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
from swirui.rendering import Point, Rect, Scene, SceneNode, SceneNodeKind
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


def _key(window: Window, kind: PlatformEventKind, key_code: int) -> None:
    window._apply_platform_event(
        PlatformEvent(kind, NativeWindowHandle(1), key_code=key_code)
    )


def test_checkbox_compiles_retained_visuals_and_checked_semantics() -> None:
    root = Component("root")
    checkbox = Checkbox(
        "Enable GPU effects",
        key="effects",
        bounds=Rect(20.0, 24.0, 260.0, 40.0),
        checked=True,
    )
    root.add(checkbox)

    scene = compile_component_scene(root, width=400.0, height=180.0)
    tree = build_accessibility_tree(root)

    assert scene is not None
    hit = scene.hit_test(Point(120.0, 44.0))
    assert hit is not None
    assert hit.key == "effects"
    assert _node(scene, "effects:indicator").hit_testable is False
    assert _node(scene, "effects:mark").kind is SceneNodeKind.PATH
    assert _node(scene, "effects:label").text == "Enable GPU effects"
    assert tree is not None
    semantics = tree.find("effects")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.CHECKBOX
    assert semantics.name == "Enable GPU effects"
    assert semantics.checked is True


@pytest.mark.parametrize("size", [(22, 22), (22, 12), (12, 22)])
def test_checkmark_fits_face_and_follows_inherited_palette(size):
    w, h = size
    window = Window()
    root = Component(theme=FUTURE_DARK)
    checkbox = Checkbox("", key="choice", checked=True, bounds=Rect(8, 10, w, h))
    root.add(checkbox)
    mount(window, root)
    for theme in (FUTURE_DARK, FUTURE_LIGHT):
        root.theme = theme
        for enabled in (True, False):
            checkbox.enabled = enabled
            if enabled:
                window.focus_component(checkbox)
            mark = _node(window.scene, "choice:mark")
            face = _node(window.scene, "choice:indicator").bounds
            assert mark.fill == theme.surface_color("on_accent" if enabled else "disabled_text")
            assert not mark.hit_testable
            assert (face.x < mark.bounds.x < mark.bounds.right < face.right
                    and face.y < mark.bounds.y < mark.bounds.bottom < face.bottom)
            assert mark.bounds.x - face.x == pytest.approx(face.right - mark.bounds.right)
            assert mark.bounds.y - face.y == pytest.approx(face.bottom - mark.bounds.bottom)
            assert checkbox.accessible_checked
    checkbox.checked = False
    assert not any(n.key == "choice:mark" for n in window.scene.walk())


def test_locked_radio_dot_and_switch_thumb_follow_the_inherited_disabled_palette():
    root = Component(theme=FUTURE_DARK)
    radio = RadioButton("Balanced", key="quality", bounds=Rect(10, 10, 180, 36), checked=True)
    switch = Switch("Refresh", key="refresh", bounds=Rect(10, 60, 180, 36))
    root.add(radio, switch)
    window = Window()
    mount(window, root)
    radio.enabled = switch.enabled = False
    for theme in (FUTURE_LIGHT, FUTURE_DARK):
        root.theme = theme
        assert _node(window.scene, "quality:mark").fill == theme.surface_color("disabled_text")
        for checked in (True, False):
            switch.checked = checked
            knob = _node(window.scene, "refresh:knob")
            assert knob.fill == theme.surface_color("disabled_text")
            assert switch.accessible_checked is checked
            switch.enabled = True
            enabled_knob = _node(window.scene, "refresh:knob")
            assert enabled_knob.fill == theme.surface_color("on_accent" if checked else "text")
            assert enabled_knob.bounds == knob.bounds
            switch.enabled = False
    radio.enabled = True
    assert _node(window.scene, "quality:mark").fill == FUTURE_DARK.surface_color("on_accent")


def test_checkbox_pointer_activation_emits_change_and_rebuilds_scene() -> None:
    window = Window(width=420, height=220)
    root = Component("root")
    checkbox = Checkbox(
        "Telemetry",
        key="telemetry",
        bounds=Rect(20.0, 20.0, 220.0, 40.0),
    )
    root.add(checkbox)
    runtime = mount(window, root)
    changes: list[Event] = []
    checkbox.on("changed", changes.append)
    initial_generation = runtime.generation

    _pointer(window, PlatformEventKind.POINTER_DOWN, x=90.0, y=40.0)
    assert window.focused_component is checkbox
    assert checkbox.pressed is True
    _pointer(window, PlatformEventKind.POINTER_UP, x=90.0, y=40.0)

    assert checkbox.checked is True
    assert checkbox.pressed is False
    assert len(changes) == 1
    assert changes[0].data["old_checked"] is False
    assert changes[0].data["checked"] is True
    assert runtime.generation > initial_generation
    assert window.scene is not None
    assert _node(window.scene, "telemetry:mark")


def test_switch_keyboard_activation_updates_knob_and_semantics() -> None:
    window = Window(width=420, height=220)
    root = Component("root")
    switch = Switch(
        "High refresh mode",
        key="refresh",
        bounds=Rect(20.0, 20.0, 260.0, 40.0),
    )
    root.add(switch)
    mount(window, root)
    window.focus_component(switch)
    assert window.focused_component is switch
    assert window.scene is not None
    before = _node(window.scene, "refresh:knob").bounds.x

    _key(window, PlatformEventKind.KEY_DOWN, 0x20)
    assert switch.pressed is True
    _key(window, PlatformEventKind.KEY_UP, 0x20)

    assert switch.checked is True
    assert switch.pressed is False
    assert window.scene is not None
    after = _node(window.scene, "refresh:knob").bounds.x
    assert after > before
    tree = build_accessibility_tree(root, focused=switch)
    assert tree is not None
    semantics = tree.find("refresh")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.SWITCH
    assert semantics.checked is True
    assert semantics.focused is True


def test_radio_group_keeps_one_checked_and_emits_both_state_changes() -> None:
    root = Component("quality")
    balanced = RadioButton(
        "Balanced",
        key="balanced",
        bounds=Rect(20.0, 20.0, 200.0, 40.0),
        checked=True,
        group="quality",
    )
    quality = RadioButton(
        "Quality",
        key="quality",
        bounds=Rect(20.0, 70.0, 200.0, 40.0),
        group="quality",
    )
    unrelated = RadioButton(
        "Other group",
        key="other",
        bounds=Rect(20.0, 120.0, 200.0, 40.0),
        checked=True,
        group="other",
    )
    root.add(balanced, quality, unrelated)
    balanced_changes: list[Event] = []
    quality_changes: list[Event] = []
    balanced.on("changed", balanced_changes.append)
    quality.on("changed", quality_changes.append)

    quality.checked = True

    assert quality.checked is True
    assert balanced.checked is False
    assert unrelated.checked is True
    assert len(balanced_changes) == 1
    assert balanced_changes[0].data["checked"] is False
    assert len(quality_changes) == 1
    assert quality_changes[0].data["checked"] is True


@pytest.mark.parametrize(("backend", "arrows", "ordinary_key"), [
    ("win32", (0x25, 0x26, 0x27, 0x28), 0x7B),
    ("x11", (0xFF51, 0xFF52, 0xFF53, 0xFF54), 0x25),
    ("cocoa", (0x7B, 0x7E, 0x7C, 0x7D), 0x25),
])
def test_radio_arrows_move_selection_and_focus_within_the_current_group(
    backend, arrows, ordinary_key,
):
    window, root = Window(), Component()
    rect = Rect(10, 10, 120, 32)
    first, disabled, hidden, unfocusable, middle, last = [
        RadioButton(label, bounds=rect) for label in ("A", "B", "C", "D", "E", "F")
    ]
    disabled.enabled = False
    hidden.visible = False
    unfocusable.focusable = False
    other = RadioButton("Other", group="secondary", bounds=rect, checked=True)
    nested = RadioButton("Nested", bounds=rect, checked=True)
    root.add(first, disabled, hidden, other, Component().add(nested), unfocusable, middle, last)
    mount(window, root)
    window._platform_backend = SimpleNamespace(name=backend)
    first.checked = True
    window.focus_component(first)
    changes = []
    middle.on("changed", changes.append)
    left, up, right, down = arrows
    for modifier in ("shift", "ctrl", "alt", "meta"):
        window._apply_platform_event(PlatformEvent(
            PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=down, **{modifier: True}
        ))
    _key(window, PlatformEventKind.KEY_DOWN, ordinary_key)
    assert window.focused_component is first and first.checked and not changes
    for key, target in ((down, middle), (right, last), (right, first), (up, last), (left, middle)):
        _key(window, PlatformEventKind.KEY_DOWN, key)
        _key(window, PlatformEventKind.KEY_UP, key)
        assert window.focused_component is target and target.accessible_checked
        assert [option for option in (first, middle, last) if option.checked] == [target]
        assert other.checked and nested.checked
    assert [event.data["checked"] for event in changes] == [True, False, True]
    assert changes[0].data["input_event"].source is first
    _key(window, PlatformEventKind.KEY_DOWN, 0x09)
    assert window.focused_component is last


def test_radio_arrow_respects_cancelled_keys_and_focus_redirects():
    window, root = Window(), Component()
    first = RadioButton("A", bounds=Rect(0, 0, 120, 32), checked=True)
    second = RadioButton("B", bounds=Rect(0, 40, 120, 32))
    after = Checkbox("Next", bounds=Rect(0, 80, 120, 32))
    root.add(first, second, after)
    mount(window, root)
    window.focus_component(first)
    cancel = root.on("key_down", lambda ev: ev.prevent_default(), capture=True)
    _key(window, PlatformEventKind.KEY_DOWN, 0x28)
    assert window.focused_component is first and first.checked
    cancel()
    lock = root.on("key_down", lambda _: root.set_enabled(False), capture=True)
    _key(window, PlatformEventKind.KEY_DOWN, 0x28)
    assert first.checked and not second.checked
    lock()
    root.enabled = True
    window.focus_component(first)
    second.on("focus_gained", lambda _: window.focus_component(after))
    _key(window, PlatformEventKind.KEY_DOWN, 0x28)
    assert window.focused_component is after and first.checked and not second.checked


def test_disabled_toggle_is_semantic_but_not_interactive() -> None:
    window = Window(width=360, height=180)
    root = Component("root")
    checkbox = Checkbox(
        "Locked",
        key="locked",
        bounds=Rect(20.0, 20.0, 180.0, 40.0),
    )
    checkbox.enabled = False
    root.add(checkbox)
    mount(window, root)

    _pointer(window, PlatformEventKind.POINTER_DOWN, x=60.0, y=40.0)
    _pointer(window, PlatformEventKind.POINTER_UP, x=60.0, y=40.0)

    assert checkbox.checked is False
    assert window.focused_component is None
    assert window.scene is not None
    assert _node(window.scene, "locked").hit_testable is False
    tree = build_accessibility_tree(root)
    assert tree is not None
    semantics = tree.find("locked")
    assert semantics is not None
    assert semantics.enabled is False
    assert semantics.checked is False


def test_toggle_text_updates_automatic_accessible_name() -> None:
    checkbox = Checkbox("Old label", bounds=Rect(0.0, 0.0, 180.0, 40.0))

    checkbox.text = "New label"

    assert checkbox.accessible_name == "New label"


@pytest.mark.parametrize("control", [Checkbox, RadioButton, Switch])
@pytest.mark.parametrize("checked", [False, True])
def test_tab_focus_outlines_toggle_without_moving_label_or_hit_target(control, checked):
    window = Window()
    root = Component(theme=FUTURE_DARK)
    widget = control("Motion", key="option", bounds=Rect(12, 14, 160, 38), checked=checked)
    following = Checkbox("Next", bounds=Rect(12, 60, 160, 38))
    root.add(widget, following)
    mount(window, root)
    initial_label = _node(window.scene, "option:label").bounds
    face_key = "option:track" if control is Switch else "option:indicator"
    footprint = _node(window.scene, face_key).bounds
    _key(window, PlatformEventKind.KEY_DOWN, 0x09)
    assert window.focused_component is widget
    for theme in (FUTURE_DARK, FUTURE_LIGHT):
        root.theme = theme
        ring = _node(window.scene, "option:focus")
        assert ring.bounds == footprint and ring.fill == theme.surface_color("focus")
        assert not ring.hit_testable
        assert _node(window.scene, "option:focus-gap").fill == theme.surface_color("canvas")
        assert _node(window.scene, "option:label").bounds == initial_label
        assert window.scene.hit_test(Point(13, 33)).key == "option"
        assert widget.checked == widget.accessible_checked == checked
    _key(window, PlatformEventKind.KEY_DOWN, 0x09)
    assert window.focused_component is following
    assert not any(n.key == "option:focus" for n in window.scene.walk())
    assert _node(window.scene, face_key).bounds == footprint


def test_compact_standalone_switch_keeps_thumb_and_drops_focus_cue_when_disabled():
    window = Window()
    switch = Switch("", key="compact", bounds=Rect(0, 0, 18, 10), checked=True)
    mount(window, switch)
    window.focus_component(switch)
    ring = _node(window.scene, "compact:focus").bounds
    face = _node(window.scene, "compact:track").bounds
    knob = _node(window.scene, "compact:knob").bounds
    assert ring == switch.bounds and knob.width > 0
    assert face.x < knob.x < knob.right < face.right
    switch.enabled = False
    assert not any(n.key.startswith("compact:focus") for n in window.scene.walk())
    assert switch.checked


def test_switch_reverses_from_the_visible_position_and_commits_each_change_immediately():
    window = Window()
    clock = AnimationController(App(), window)
    root = Component(theme=replace(FUTURE_DARK, motion_duration=1))
    switch = Switch("Sync", bounds=Rect(0, 0, 120, 22), key="sync", animations=clock)
    root.add(switch)
    mount(window, root)
    changes = []
    switch.on("changed", lambda e: changes.append((e.data["checked"], switch.accessible_checked)))
    window.focus_component(switch)

    def x():
        return _node(window.scene, "sync:knob").bounds.x

    start = x()
    label = _node(window.scene, "sync:label").bounds
    _key(window, PlatformEventKind.KEY_DOWN, 0x20)
    _key(window, PlatformEventKind.KEY_UP, 0x20)
    assert changes == [(True, True)] and x() == start
    assert clock.tick(.25) == 1
    first = x()
    clock.tick(.25)
    middle = x()
    assert start < first < middle
    switch.checked = False
    assert x() == middle and changes[-1] == (False, False)
    assert clock.tick(.25) == 1
    assert start < x() < middle
    assert clock.tick(.25) == 0 and x() == start
    switch.checked = True
    clock.tick(.5)
    assert x() == pytest.approx(middle)
    assert clock.tick(.5) == 0 and x() == pytest.approx(2 * middle - start)
    assert len(changes) == 3 and _node(window.scene, "sync:label").bounds == label
    assert window.focused_component is switch
    clock.dispose()


@pytest.mark.parametrize("interrupt", ["reduced", "duration", "disabled", "hidden",
                                        "unmount", "dispose"])
def test_switch_finishes_travel_when_motion_stops(interrupt):
    window = Window()
    clock = AnimationController(App(), window)
    root = Component(theme=replace(FUTURE_LIGHT, motion_duration=1))
    switch = Switch("Sync", bounds=Rect(0, 0, 140, 22), key="sync", animations=clock)
    root.add(switch)
    mount(window, root)
    switch.checked = True
    assert clock.tick(.5) == 1

    def knob_x():
        return next(n.bounds.x for n in switch.build_scene_node().walk() if n.key == "sync:knob")

    halfway = knob_x()
    if interrupt == "reduced":
        root.theme = replace(root.theme, reduced_motion=True)
    elif interrupt == "duration":
        root.theme = replace(root.theme, motion_duration=0)
    elif interrupt == "disabled":
        switch.enabled = False
    elif interrupt == "hidden":
        switch.visible = False
    elif interrupt == "unmount":
        root.remove(switch)
    else:
        clock.dispose()
    assert clock.active_count == 0 and switch.accessible_checked
    assert knob_x() > halfway
    switch.checked = False
    assert clock.active_count == 0 and not switch.accessible_checked
    assert knob_x() < halfway
    clock.dispose()
