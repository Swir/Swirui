from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationController,
    App,
    Button,
    MagneticInteraction,
    MagneticInteractionSpec,
    Panel,
    Window,
)
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind
from swirui.rendering import NullRenderer, Point, Rect
from swirui.widgets.runtime import compile_component_scene


def _runtime() -> tuple[AnimationController, Button, MagneticInteraction]:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(title="Magnetic interaction"))
    button = Button("Magnetic", bounds=Rect(100.0, 80.0, 200.0, 60.0))
    controller = AnimationController(app, window)
    interaction = MagneticInteraction(controller, button)
    return controller, button, interaction


def _move(button: Button, x: float, y: float) -> None:
    button.emit(
        "pointer_move",
        event=PlatformEvent(PlatformEventKind.POINTER_MOVE, object(), x=x, y=y),
    )


def test_visual_offset_translates_complete_subtree_without_mutating_layout() -> None:
    panel = Panel(bounds=Rect(20.0, 30.0, 300.0, 160.0), key="panel", clip_to_bounds=True)
    button = Button("Child", bounds=Rect(50.0, 70.0, 120.0, 40.0), key="child")
    panel.add(button)
    preferred = panel.preferred_size
    arranged = panel.bounds

    panel.visual_offset = Point(12.0, -8.0)
    scene = compile_component_scene(panel, width=640.0, height=400.0)

    assert scene is not None
    panel_node = next(node for node in scene.walk() if node.key == "panel")
    child_node = next(node for node in scene.walk() if node.key == "child")
    assert panel_node.bounds == Rect(32.0, 22.0, 300.0, 160.0)
    assert child_node.bounds == Rect(62.0, 62.0, 120.0, 40.0)
    assert panel.bounds == arranged
    assert panel.preferred_size == preferred
    assert scene.hit_test_xy(70.0, 70.0) is child_node
    assert scene.hit_test_xy(52.0, 72.0) is not child_node


def test_visual_offset_requires_finite_coordinates() -> None:
    button = Button("Finite", bounds=Rect(0.0, 0.0, 120.0, 40.0))

    with pytest.raises(ValueError, match="visual_offset"):
        button.visual_offset = Point(math.inf, 0.0)
    with pytest.raises(ValueError, match="visual_offset"):
        button.set_visual_offset(0.0, math.nan)


def test_magnetic_interaction_clamps_target_and_springs_to_pointer() -> None:
    controller, button, interaction = _runtime()

    _move(button, 300.0, 110.0)
    assert interaction.target_offset == Point(12.0, 0.0)
    assert interaction.active is True
    controller.tick(interaction.spec.max_duration)

    assert button.visual_offset.x == pytest.approx(12.0)
    assert button.visual_offset.y == pytest.approx(0.0)
    assert interaction.active is False


def test_magnetic_interaction_retargets_from_current_presented_offset() -> None:
    controller, button, interaction = _runtime()

    _move(button, 300.0, 110.0)
    controller.tick(0.04)
    midpoint = button.visual_offset.x
    assert 0.0 < midpoint < 12.0

    _move(button, 100.0, 110.0)
    assert button.visual_offset.x == pytest.approx(midpoint)
    assert interaction.target_offset == Point(-12.0, 0.0)
    controller.tick(interaction.spec.max_duration)
    assert button.visual_offset.x == pytest.approx(-12.0)


def test_pointer_leave_disable_and_dispose_restore_authored_idle_offset() -> None:
    controller, button, interaction = _runtime()
    button.visual_offset = Point(2.0, 3.0)
    interaction.dispose()

    interaction = MagneticInteraction(controller, button)
    _move(button, 300.0, 110.0)
    controller.tick(0.04)
    assert button.visual_offset != Point(2.0, 3.0)

    button.emit("pointer_leave")
    controller.tick(interaction.spec.max_duration)
    assert button.visual_offset == Point(2.0, 3.0)

    _move(button, 300.0, 110.0)
    controller.tick(0.04)
    button.enabled = False
    controller.tick(interaction.spec.max_duration)
    assert button.visual_offset == Point(2.0, 3.0)

    button.enabled = True
    _move(button, 300.0, 110.0)
    controller.tick(0.04)
    interaction.dispose()
    assert interaction.disposed is True
    assert interaction.active is False
    assert button.visual_offset == Point(2.0, 3.0)


def test_magnetic_interaction_spec_validates_spring_parameters() -> None:
    with pytest.raises(ValueError, match="max_offset"):
        MagneticInteractionSpec(max_offset=0.0)
    with pytest.raises(ValueError, match="mass"):
        MagneticInteractionSpec(mass=math.nan)
    with pytest.raises(ValueError, match="stiffness"):
        MagneticInteractionSpec(stiffness=-1.0)
    with pytest.raises(ValueError, match="damping"):
        MagneticInteractionSpec(damping=-1.0)
    with pytest.raises(ValueError, match="max_duration"):
        MagneticInteractionSpec(max_duration=0.0)
