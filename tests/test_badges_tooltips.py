import pytest

from swirui import Badge, Button, Chip, Component, Tooltip, Window, build_accessibility_tree, mount
from swirui.core import AccessibilityRole, Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Color, Point, Rect, SceneNodeKind
from swirui.widgets import compile_component_scene


def test_badge_compiles_retained_pill_and_tracks_semantic_text() -> None:
    root = Component("root")
    badge = Badge(
        "Alpha",
        key="status-badge",
        bounds=Rect(12.0, 16.0, 92.0, 28.0),
        background=Color.from_hex("#113047"),
    )
    root.add(badge)
    invalidations: list[Event] = []
    root.on("invalidated", invalidations.append)

    scene = compile_component_scene(root, width=320.0, height=180.0)

    assert scene is not None
    pill = next(node for node in scene.walk() if node.key == "status-badge")
    text = next(node for node in scene.walk() if node.key == "status-badge:text")
    assert pill.kind is SceneNodeKind.RECTANGLE
    assert pill.hit_testable is False
    assert text.kind is SceneNodeKind.TEXT
    assert text.text == "Alpha"
    assert badge.accessibility_role is AccessibilityRole.TEXT
    assert badge.accessible_name == "Alpha"

    badge.text = "Beta"

    assert badge.accessible_name == "Beta"
    assert invalidations[-1].data["component"] is badge
    assert invalidations[-1].data["reason"] == "text"


def test_chip_toggles_with_routed_pointer_and_keyboard_input() -> None:
    window = Window(width=420, height=240)
    root = Component("root")
    chip = Chip(
        "GPU",
        key="gpu-chip",
        bounds=Rect(28.0, 32.0, 120.0, 40.0),
        accessible_name="GPU mode",
    )
    root.add(chip)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)
    changes: list[Event] = []
    chip.on("selection_changed", changes.append)

    assert window.scene is not None
    assert window.scene.hit_test(Point(40.0, 44.0)) is not None
    assert chip.selected is False
    assert chip.accessibility_role is AccessibilityRole.CHIP
    assert chip.accessible_checked is False

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=40.0,
            y=44.0,
            button=PointerButton.LEFT,
        )
    )
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_UP,
            handle,
            x=40.0,
            y=44.0,
            button=PointerButton.LEFT,
        )
    )

    assert window.focused_component is chip
    assert chip.selected is True
    assert chip.accessible_checked is True
    assert changes[-1].data["selected"] is True

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=0x20)
    )
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_UP, handle, key_code=0x20)
    )

    assert chip.selected is False
    assert chip.accessible_checked is False
    assert changes[-1].data["selected"] is False
    assert runtime.generation >= 3


def test_chip_programmatic_selection_rejects_noop_duplicate_events() -> None:
    chip = Chip("Pinned", bounds=Rect(0.0, 0.0, 100.0, 36.0))
    changes: list[Event] = []
    chip.on("selection_changed", changes.append)

    chip.selected = True
    chip.selected = True
    chip.selected = False

    assert [event.data["selected"] for event in changes] == [True, False]


def test_tooltip_follows_target_hover_and_focus_without_stealing_hits() -> None:
    window = Window(width=480, height=260)
    root = Component("root")
    button = Button("Inspect", key="inspect", bounds=Rect(30.0, 30.0, 140.0, 44.0))
    tooltip = Tooltip(
        "Inspect retained node",
        key="inspect-tip",
        target=button,
        bounds=Rect(30.0, 84.0, 190.0, 34.0),
    )
    root.add(button, tooltip)
    runtime = mount(window, root)
    handle = NativeWindowHandle(1)

    assert tooltip.is_open is False
    assert window.scene is not None
    assert all(node.key != tooltip.key for node in window.scene.walk())

    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=50.0, y=48.0)
    )

    assert tooltip.is_open is True
    assert window.scene is not None
    tip_node = next(node for node in window.scene.walk() if node.key == tooltip.key)
    assert tip_node.hit_testable is False
    assert window.scene.hit_test(Point(50.0, 96.0)) is None

    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=50.0,
            y=48.0,
            button=PointerButton.LEFT,
        )
    )
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=300.0, y=180.0)
    )

    assert window.focused_component is button
    assert tooltip.is_open is True

    window.focus_component(None)

    assert tooltip.is_open is False
    assert runtime.generation >= 4


def test_tooltip_semantics_are_visible_only_while_open() -> None:
    root = Component("root")
    tooltip = Tooltip(
        "Keyboard help",
        key="help-tip",
        bounds=Rect(10.0, 10.0, 160.0, 32.0),
        initially_open=False,
    )
    root.add(tooltip)

    hidden_tree = build_accessibility_tree(root)
    assert hidden_tree is not None
    assert hidden_tree.find("help-tip") is None

    tooltip.show()
    visible_tree = build_accessibility_tree(root)
    assert visible_tree is not None
    node = visible_tree.find("help-tip")
    assert node is not None
    assert node.role is AccessibilityRole.TOOLTIP
    assert node.name == "Keyboard help"


def test_badge_and_tooltip_validation_reject_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="font_size"):
        Badge("bad", bounds=Rect(0.0, 0.0, 80.0, 24.0), font_size=0.0)
    with pytest.raises(ValueError, match="padding"):
        Tooltip("bad", bounds=Rect(0.0, 0.0, 100.0, 30.0), padding=float("nan"))
