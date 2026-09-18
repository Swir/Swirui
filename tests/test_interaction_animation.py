from __future__ import annotations

import math

import pytest

from swirui import (
    AnimationController,
    App,
    Button,
    InteractionAnimationSpec,
    InteractionAnimator,
    InteractionPhase,
    Window,
)
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer, Rect


def _runtime() -> tuple[AnimationController, Button, InteractionAnimator]:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(title="Interaction animation"))
    button = Button("Animate me", bounds=Rect(0.0, 0.0, 180.0, 48.0))
    animator = InteractionAnimator(AnimationController(app, window), button)
    return animator.controller, button, animator


def test_interaction_animator_resolves_hover_press_and_focus_priority() -> None:
    controller, button, animator = _runtime()

    button.emit("focus_gained")
    controller.tick(0.10)
    assert animator.phase is InteractionPhase.FOCUSED
    assert button.opacity == pytest.approx(0.92)

    button.emit("pointer_enter")
    controller.tick(0.10)
    assert animator.phase is InteractionPhase.HOVERED
    assert button.opacity == pytest.approx(0.96)

    button.emit("pointer_down")
    controller.tick(0.10)
    assert animator.phase is InteractionPhase.PRESSED
    assert button.opacity == pytest.approx(0.82)

    button.emit("pointer_up")
    controller.tick(0.16)
    assert animator.phase is InteractionPhase.HOVERED
    assert button.opacity == pytest.approx(0.96)

    button.emit("pointer_leave")
    controller.tick(0.16)
    assert animator.phase is InteractionPhase.FOCUSED
    assert button.opacity == pytest.approx(0.92)

    button.emit("focus_lost")
    controller.tick(0.16)
    assert animator.phase is InteractionPhase.IDLE
    assert button.opacity == pytest.approx(1.0)


def test_interaction_animator_retargets_from_current_presented_sample() -> None:
    controller, button, animator = _runtime()

    button.emit("pointer_enter")
    controller.tick(0.05)
    hovered_midpoint = button.opacity
    assert 0.96 < hovered_midpoint < 1.0

    button.emit("pointer_down")
    assert button.opacity == pytest.approx(hovered_midpoint)
    controller.tick(0.05)

    assert animator.phase is InteractionPhase.PRESSED
    assert 0.82 < button.opacity < hovered_midpoint
    controller.tick(0.05)
    assert button.opacity == pytest.approx(0.82)


def test_disabling_widget_clears_transient_state_and_restores_idle_target() -> None:
    controller, button, animator = _runtime()

    button.emit("pointer_enter")
    button.emit("pointer_down")
    controller.tick(0.10)
    assert button.opacity == pytest.approx(0.82)

    button.enabled = False
    assert animator.phase is InteractionPhase.IDLE
    controller.tick(0.16)
    assert button.opacity == pytest.approx(1.0)


def test_dispose_detaches_listeners_cancels_animation_and_restores_idle() -> None:
    controller, button, animator = _runtime()

    button.emit("pointer_enter")
    controller.tick(0.04)
    assert animator.active is True

    animator.dispose()
    assert animator.disposed is True
    assert animator.active is False
    assert animator.phase is InteractionPhase.IDLE
    assert button.opacity == pytest.approx(1.0)

    button.emit("pointer_down")
    controller.tick(1.0)
    assert button.opacity == pytest.approx(1.0)


def test_interaction_animation_spec_validates_opacity_and_time() -> None:
    with pytest.raises(ValueError, match="hover_opacity"):
        InteractionAnimationSpec(hover_opacity=1.1)
    with pytest.raises(ValueError, match="pressed_opacity"):
        InteractionAnimationSpec(pressed_opacity=math.nan)
    with pytest.raises(ValueError, match="duration"):
        InteractionAnimationSpec(duration=-0.01)


def test_zero_duration_interactions_complete_synchronously() -> None:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window())
    button = Button("Instant", bounds=Rect(0.0, 0.0, 120.0, 40.0))
    controller = AnimationController(app, window)
    animator = InteractionAnimator(
        controller,
        button,
        spec=InteractionAnimationSpec(duration=0.0, release_duration=0.0),
    )

    button.emit("pointer_enter")
    assert button.opacity == pytest.approx(0.96)
    assert controller.active_count == 0

    button.emit("pointer_down")
    assert button.opacity == pytest.approx(0.82)
    assert controller.active_count == 0

    button.emit("pointer_leave")
    assert button.opacity == pytest.approx(1.0)
    assert controller.active_count == 0
    assert animator.phase is InteractionPhase.IDLE
