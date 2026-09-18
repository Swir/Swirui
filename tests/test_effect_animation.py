import pytest

from swirui import AnimationStatus, BackdropBlurTransition, GlowTransition, linear
from swirui.rendering import BackdropBlur, Color, CornerRadius, Glow


def test_glow_transition_interpolates_retained_descriptor() -> None:
    samples: list[Glow] = []
    source = Glow(
        color=Color(0.0, 0.2, 0.8, 0.2),
        blur_radius=8.0,
        spread=1.0,
        steps=8,
    )
    target = Glow(
        color=Color(0.2, 0.9, 1.0, 0.7),
        blur_radius=24.0,
        spread=5.0,
        steps=8,
    )
    transition = GlowTransition(source, target, 1.0, samples.append, easing=linear)

    transition.start()
    assert samples[-1] == source
    transition.advance(0.5)
    midpoint = samples[-1]
    assert midpoint.color.r == pytest.approx(0.1)
    assert midpoint.color.g == pytest.approx(0.55)
    assert midpoint.color.b == pytest.approx(0.9)
    assert midpoint.color.a == pytest.approx(0.45)
    assert midpoint.blur_radius == pytest.approx(16.0)
    assert midpoint.spread == pytest.approx(3.0)
    assert midpoint.steps == 8

    assert transition.advance(0.75) == pytest.approx(0.25)
    assert transition.status is AnimationStatus.COMPLETED
    assert samples[-1] == target


def test_glow_transition_is_frame_partition_independent() -> None:
    source = Glow(blur_radius=4.0, spread=2.0, steps=12)
    target = Glow(blur_radius=28.0, spread=6.0, steps=12)
    direct: list[Glow] = []
    partitioned: list[Glow] = []
    one = GlowTransition(source, target, 1.0, direct.append, easing=linear).start()
    two = GlowTransition(source, target, 1.0, partitioned.append, easing=linear).start()

    one.advance(0.625)
    for delta in (0.1, 0.2, 0.075, 0.25):
        two.advance(delta)

    assert direct[-1] == partitioned[-1]
    assert one.elapsed == pytest.approx(two.elapsed)
    assert one.progress == pytest.approx(two.progress)


def test_glow_transition_requires_stable_retained_layer_budget() -> None:
    with pytest.raises(ValueError, match="matching steps"):
        GlowTransition(Glow(steps=4), Glow(steps=12), 0.2, lambda _value: None)


def test_backdrop_blur_transition_interpolates_radius_and_corner_geometry() -> None:
    samples: list[BackdropBlur] = []
    source = BackdropBlur(radius=6.0, corner_radius=CornerRadius(2.0, 4.0, 6.0, 8.0))
    target = BackdropBlur(radius=30.0, corner_radius=CornerRadius(10.0, 12.0, 14.0, 16.0))
    transition = BackdropBlurTransition(source, target, 2.0, samples.append, easing=linear)

    transition.start()
    transition.advance(0.5)
    sample = samples[-1]
    assert sample.radius == pytest.approx(12.0)
    assert sample.corner_radius == CornerRadius(4.0, 6.0, 8.0, 10.0)

    transition.advance(1.5)
    assert transition.status is AnimationStatus.COMPLETED
    assert samples[-1] == target


def test_effect_transition_cancellation_preserves_current_visual_sample() -> None:
    samples: list[Glow] = []
    transition = GlowTransition(
        Glow(blur_radius=8.0, steps=8),
        Glow(blur_radius=40.0, steps=8),
        1.0,
        samples.append,
        easing=linear,
    ).start()

    transition.advance(0.25)
    current = samples[-1]
    assert transition.cancel() is True
    assert transition.status is AnimationStatus.CANCELLED
    assert transition.advance(1.0) == pytest.approx(1.0)
    assert samples[-1] == current
