from swirui import Badge, Chip, Component, Tooltip, Window, build_accessibility_tree, mount
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


def test_badge_compiles_status_semantics_and_updates_accessible_name() -> None:
    root = Component("root")
    badge = Badge("ALPHA", key="status", bounds=Rect(12.0, 16.0, 88.0, 28.0))
    root.add(badge)
    invalidations: list[Event] = []
    root.on("invalidated", invalidations.append)

    scene = compile_component_scene(root, width=240.0, height=120.0)
    tree = build_accessibility_tree(root)

    assert scene is not None
    assert _node(scene, "status").hit_testable is False
    assert _node(scene, "status:content").text == "ALPHA"
    assert scene.hit_test(Point(30.0, 30.0)) is None
    assert tree is not None
    semantics = tree.find("status")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.STATUS
    assert semantics.name == "ALPHA"

    badge.text = "BETA"
    assert badge.accessible_name == "BETA"
    assert invalidations[-1].data["reason"] == "text"


def test_chip_routes_pointer_activation_through_retained_runtime() -> None:
    window = Window(width=320, height=140)
    root = Component("root")
    chip = Chip("Filters", key="filters", bounds=Rect(24.0, 24.0, 110.0, 34.0))
    root.add(chip)
    runtime = mount(window, root)
    clicks: list[Event] = []
    chip.on("click", clicks.append)
    initial_generation = runtime.generation

    _pointer(window, PlatformEventKind.POINTER_DOWN, x=60.0, y=40.0)
    _pointer(window, PlatformEventKind.POINTER_UP, x=60.0, y=40.0)

    assert window.focused_component is chip
    assert len(clicks) == 1
    assert runtime.generation > initial_generation
    tree = build_accessibility_tree(root, focused=chip)
    assert tree is not None
    semantics = tree.find("filters")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.BUTTON
    assert semantics.focused is True


def test_tooltip_tracks_hover_and_focus_without_stealing_hits() -> None:
    root = Component("root")
    chip = Chip("Help", key="help", bounds=Rect(20.0, 20.0, 90.0, 34.0))
    tooltip = Tooltip(
        "Open help",
        target=chip,
        key="help-tip",
        bounds=Rect(20.0, 64.0, 150.0, 34.0),
    )
    root.add(chip, tooltip)

    assert tooltip.visible is False
    initial = compile_component_scene(root, width=260.0, height=140.0)
    assert initial is not None
    assert all(node.key != "help-tip" for node in initial.walk())

    chip.emit("pointer_enter")
    assert tooltip.visible is True
    hovered = compile_component_scene(root, width=260.0, height=140.0)
    assert hovered is not None
    assert _node(hovered, "help-tip").hit_testable is False
    assert hovered.hit_test(Point(30.0, 74.0)) is None
    tree = build_accessibility_tree(root)
    assert tree is not None
    semantics = tree.find("help-tip")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.TOOLTIP
    assert semantics.name == "Open help"

    chip.emit("pointer_leave")
    assert tooltip.visible is False
    chip.emit("focus_gained")
    assert tooltip.visible is True
    tooltip.show_on_focus = False
    assert tooltip.visible is False


def test_tooltip_hides_when_target_becomes_disabled_or_hidden() -> None:
    chip = Chip("Target", bounds=Rect(0.0, 0.0, 100.0, 32.0))
    tooltip = Tooltip(
        "Target tooltip",
        target=chip,
        bounds=Rect(0.0, 40.0, 160.0, 32.0),
    )

    chip.emit("pointer_enter")
    assert tooltip.visible is True
    chip.enabled = False
    assert tooltip.visible is False

    chip.enabled = True
    chip.emit("focus_gained")
    assert tooltip.visible is True
    chip.visible = False
    assert tooltip.visible is False


def test_tooltip_detach_stops_target_tracking() -> None:
    chip = Chip("Detached", bounds=Rect(0.0, 0.0, 100.0, 32.0))
    tooltip = Tooltip(
        "Detached tooltip",
        target=chip,
        bounds=Rect(0.0, 40.0, 160.0, 32.0),
    )

    chip.emit("pointer_enter")
    assert tooltip.visible is True
    tooltip.detach()
    assert tooltip.visible is False
    chip.emit("pointer_enter")
    chip.emit("focus_gained")
    assert tooltip.visible is False
