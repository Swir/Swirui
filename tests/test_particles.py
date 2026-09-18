from __future__ import annotations

import math

import pytest

from swirui import AnimationController, AnimationStatus, App, ParticleField, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Color, NullRenderer, Rect, SceneNodeKind


def _samples(field: ParticleField) -> tuple[tuple[float, float, float, float], ...]:
    return tuple((sample.x, sample.y, sample.size, sample.opacity) for sample in field.samples())


def test_particle_field_is_deterministic_for_seed_and_elapsed_time() -> None:
    first = ParticleField(
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        particle_count=24,
        seed=42,
    ).start()
    second = ParticleField(
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        particle_count=24,
        seed=42,
    ).start()

    first.advance(0.5)
    for _ in range(5):
        second.advance(0.1)

    left = _samples(first)
    right = _samples(second)
    assert len(left) == len(right)
    for left_sample, right_sample in zip(left, right, strict=True):
        assert left_sample == pytest.approx(right_sample, rel=1e-12, abs=1e-12)


def test_particle_seed_changes_geometry_without_global_random_state() -> None:
    first = ParticleField(bounds=Rect(0, 0, 200, 120), particle_count=12, seed=1).start()
    second = ParticleField(bounds=Rect(0, 0, 200, 120), particle_count=12, seed=2).start()

    first.advance(0.25)
    second.advance(0.25)

    assert _samples(first) != _samples(second)


def test_non_looping_particle_field_completes_and_returns_frame_tail() -> None:
    completions: list[str] = []
    field = ParticleField(
        bounds=Rect(0, 0, 200, 120),
        particle_count=8,
        seed=7,
        loop=False,
        duration=0.5,
        on_complete=lambda: completions.append("done"),
    ).start()

    unused = field.advance(0.75)
    field.advance(1.0)

    assert unused == pytest.approx(0.25)
    assert field.elapsed == pytest.approx(0.5)
    assert field.status is AnimationStatus.COMPLETED
    assert completions == ["done"]


def test_non_looping_default_duration_covers_staggered_lifetimes() -> None:
    field = ParticleField(
        bounds=Rect(0, 0, 160, 90),
        particle_count=16,
        seed=10,
        loop=False,
        lifetime_range=(0.2, 0.4),
    )

    assert field.duration is not None
    assert field.duration > 0.2
    field.start()
    field.advance(field.duration + 1.0)
    assert field.status is AnimationStatus.COMPLETED


def test_particle_scene_uses_clipped_noninteractive_gpu_batch_nodes() -> None:
    colors = (Color(0.0, 0.5, 1.0, 0.8), Color(1.0, 0.2, 0.4, 0.6))
    field = ParticleField(
        bounds=Rect(20.0, 30.0, 300.0, 160.0),
        key="particles",
        particle_count=32,
        seed=99,
        colors=colors,
        opacity=0.75,
    ).start()
    field.advance(0.37)

    node = field.build_scene_node()
    assert node.kind is SceneNodeKind.GROUP
    assert node.clip_to_bounds is True
    assert node.hit_testable is False
    assert node.opacity == pytest.approx(0.75)
    assert 0 < len(node.children) <= field.particle_count
    assert all(child.kind is SceneNodeKind.RECTANGLE for child in node.children)
    assert all(child.hit_testable is False for child in node.children)
    assert all(child.fill is not None and 0.0 < child.fill.a <= 0.8 for child in node.children)
    assert all(
        child.corner_radius.top_left == pytest.approx(child.bounds.width * 0.5)
        for child in node.children
    )


def test_particle_field_cancellation_holds_current_sample() -> None:
    field = ParticleField(bounds=Rect(0, 0, 240, 140), particle_count=16, seed=3).start()
    field.advance(0.2)
    snapshot = _samples(field)

    assert field.cancel() is True
    assert field.cancel() is False
    assert field.status is AnimationStatus.CANCELLED
    assert field.advance(1.0) == pytest.approx(1.0)
    assert _samples(field) == snapshot


def test_particle_field_validates_bounded_inputs() -> None:
    with pytest.raises(ValueError, match="positive dimensions"):
        ParticleField(bounds=Rect(0, 0, 0, 100))
    with pytest.raises(ValueError, match="particle_count"):
        ParticleField(bounds=Rect(0, 0, 100, 100), particle_count=0)
    with pytest.raises(ValueError, match="colors"):
        ParticleField(bounds=Rect(0, 0, 100, 100), colors=())
    with pytest.raises(ValueError, match="speed_range"):
        ParticleField(bounds=Rect(0, 0, 100, 100), speed_range=(-1.0, 2.0))
    with pytest.raises(ValueError, match="size_range"):
        ParticleField(bounds=Rect(0, 0, 100, 100), size_range=(0.0, 2.0))
    with pytest.raises(ValueError, match="duration"):
        ParticleField(bounds=Rect(0, 0, 100, 100), duration=math.inf)


def test_animation_controller_drives_particle_field_on_one_window_clock() -> None:
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(title="Particles"))
    other = app.add_window(Window(title="Other"))
    field = ParticleField(bounds=Rect(0, 0, 300, 180), particle_count=12, seed=5)
    controller = AnimationController(app, window)

    controller.play(field)
    app.emit("frame_rendered", window=other, frame_delta=0.25)
    assert field.elapsed == 0.0

    app.emit("frame_rendered", window=window, frame_delta=0.25)
    assert field.elapsed == pytest.approx(0.25)
    assert controller.active_count == 1

    controller.dispose()
    assert field.status is AnimationStatus.CANCELLED
