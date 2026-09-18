from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from swirui import (
    AnimationController,
    App,
    Button,
    MagneticInteractionAnimator,
    MagneticInteractionSpec,
    Window,
)
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer, Point, Rect


def _runtime(
    *,
    spec: MagneticInteractionSpec | None = None,
) -> tuple[AnimationController, Button, MagneticInteractionAnimator]:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(title="Magnetic interaction"))
    button = Button("Magnetic", bounds=Rect(100.0, 80.0, 200.0, 80.0))
    controller = AnimationController(app, window)
    animator = MagneticInteractionAnimator(controller, button, spec=spec)
    return controller, button, animator


def _move(button: Button, x: float, y: float) -> None:
    button.emit("pointer_move", event=SimpleNamespace(x=x, y=y))


def test_pointer_motion_attracts_toward_pointer_with_bounded_vector_offset() -> None:
    _, button, animator = _runtime(
        spec=MagneticInteractionSpec(strength=0.5, max_offset=20.0)
    )
    authored_bounds = button.bounds
    preferred_size = button.preferred_size

    _move(button, 300.0, 120.0)

    assert button.visual_offset == Point(20.0, 0.0)
    assert animator.offset == Point(20.0, 0.0)
    assert button.bounds == authored_bounds
    assert button.preferred_size == preferred_size

    _move(button, 300.0, 200.0)
    assert math.hypot(button.visual_offset.x, button.visual_offset.y) == pytest.approx(20.0)
    assert button.visual_offset.x > 0.0
    assert button.visual_offset.y > 0.0


def test_pointer_leave_springs_back_to_zero_on_window_animation_controller() -> None:
    controller, button, animator = _runtime()
    _move(button, 285.0, 150.0)
    attracted = button.visual_offset
    assert attracted != Point()

    button.emit("pointer_leave")
    assert animator.active is True
    controller.tick(0.08)
    assert button.visual_offset != attracted

    controller.tick(2.0)
    assert animator.active is False
    assert button.visual_offset.x == pytest.approx(0.0)
    assert button.visual_offset.y == pytest.approx(0.0)


def test_new_pointer_sample_cancels_release_and_retargets_from_layout_center() -> None:
    controller, button, animator = _runtime()
    _move(button, 290.0, 120.0)
    button.emit("pointer_leave")
    controller.tick(0.06)
    assert animator.active is True

    _move(button, 110.0, 120.0)

    assert animator.active is False
    assert button.visual_offset.x < 0.0
    assert button.bounds == Rect(100.0, 80.0, 200.0, 80.0)


def test_disabling_widget_releases_magnetic_offset() -> None:
    controller, button, animator = _runtime()
    _move(button, 285.0, 120.0)
    assert button.visual_offset != Point()

    button.enabled = False
    assert animator.active is True
    controller.tick(2.0)
    assert button.visual_offset == Point()


def test_dispose_detaches_events_and_restores_visual_offset() -> None:
    controller, button, animator = _runtime()
    _move(button, 285.0, 120.0)
    assert button.visual_offset != Point()

    animator.dispose()
    assert animator.disposed is True
    assert animator.active is False
    assert button.visual_offset == Point()

    _move(button, 290.0, 120.0)
    controller.tick(2.0)
    assert button.visual_offset == Point()


def test_invalid_or_missing_pointer_coordinates_are_ignored() -> None:
    _, button, _ = _runtime()

    button.emit("pointer_move", event=SimpleNamespace(x=math.nan, y=120.0))
    button.emit("pointer_move", event=SimpleNamespace(x=None, y=120.0))
    button.emit("pointer_move")

    assert button.visual_offset == Point()


def test_magnetic_spec_validates_strength_limits_and_spring_parameters() -> None:
    with pytest.raises(ValueError, match="strength"):
        MagneticInteractionSpec(strength=-0.1)
    with pytest.raises(ValueError, match="max_offset"):
        MagneticInteractionSpec(max_offset=math.inf)
    with pytest.raises(ValueError, match="mass"):
        MagneticInteractionSpec(mass=0.0)
    with pytest.raises(ValueError, match="stiffness"):
        MagneticInteractionSpec(stiffness=-1.0)
    with pytest.raises(ValueError, match="damping"):
        MagneticInteractionSpec(damping=-1.0)
    with pytest.raises(ValueError, match="settle_threshold"):
        MagneticInteractionSpec(settle_threshold=0.0)
    with pytest.raises(ValueError, match="max_duration"):
        MagneticInteractionSpec(max_duration=0.0)
