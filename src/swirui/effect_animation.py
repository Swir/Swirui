"""Frame-rate-independent transitions for retained blur and glow effects."""

from __future__ import annotations

from collections.abc import Callable

from .animation import AnimationStatus, Easing, Tween, ease_in_out_cubic
from .rendering import BackdropBlur, Color, CornerRadius, Glow


class GlowTransition:
    """Interpolate one retained :class:`~swirui.rendering.Glow` descriptor.

    The transition only animates visual parameters. ``steps`` is a retained
    tessellation-quality budget rather than visual state, so both endpoints must
    use the same value. This keeps the retained layer count stable throughout a
    transition and avoids quality-driven allocation churn while the persistent
    renderer context remains unchanged.
    """

    def __init__(
        self,
        from_value: Glow,
        to_value: Glow,
        duration: float,
        update: Callable[[Glow], None],
        *,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if from_value.steps != to_value.steps:
            raise ValueError(
                "GlowTransition endpoints must use matching steps; adapt both to the same "
                "quality profile before animating."
            )
        self.from_value = from_value
        self.to_value = to_value
        self.update = update
        self._tween = Tween(
            0.0,
            1.0,
            duration,
            self._publish,
            easing=easing,
            on_complete=on_complete,
        )

    @property
    def status(self) -> AnimationStatus:
        return self._tween.status

    @property
    def elapsed(self) -> float:
        return self._tween.elapsed

    @property
    def progress(self) -> float:
        return self._tween.progress

    def start(self) -> GlowTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def _publish(self, progress: float) -> None:
        self.update(
            Glow(
                color=_lerp_color(self.from_value.color, self.to_value.color, progress),
                blur_radius=_lerp(
                    self.from_value.blur_radius,
                    self.to_value.blur_radius,
                    progress,
                ),
                spread=_lerp(self.from_value.spread, self.to_value.spread, progress),
                steps=self.from_value.steps,
            )
        )


class BackdropBlurTransition:
    """Interpolate retained backdrop-blur radius and rounded clip geometry."""

    def __init__(
        self,
        from_value: BackdropBlur,
        to_value: BackdropBlur,
        duration: float,
        update: Callable[[BackdropBlur], None],
        *,
        easing: Easing = ease_in_out_cubic,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.from_value = from_value
        self.to_value = to_value
        self.update = update
        self._tween = Tween(
            0.0,
            1.0,
            duration,
            self._publish,
            easing=easing,
            on_complete=on_complete,
        )

    @property
    def status(self) -> AnimationStatus:
        return self._tween.status

    @property
    def elapsed(self) -> float:
        return self._tween.elapsed

    @property
    def progress(self) -> float:
        return self._tween.progress

    def start(self) -> BackdropBlurTransition:
        self._tween.start()
        return self

    def advance(self, delta_seconds: float) -> float:
        return self._tween.advance(delta_seconds)

    def cancel(self) -> bool:
        return self._tween.cancel()

    def _publish(self, progress: float) -> None:
        self.update(
            BackdropBlur(
                radius=_lerp(self.from_value.radius, self.to_value.radius, progress),
                corner_radius=_lerp_corner_radius(
                    self.from_value.corner_radius,
                    self.to_value.corner_radius,
                    progress,
                ),
            )
        )


def _lerp(from_value: float, to_value: float, progress: float) -> float:
    if progress <= 0.0:
        return from_value
    if progress >= 1.0:
        return to_value
    return from_value + (to_value - from_value) * progress


def _lerp_color(from_value: Color, to_value: Color, progress: float) -> Color:
    return Color(
        _lerp(from_value.r, to_value.r, progress),
        _lerp(from_value.g, to_value.g, progress),
        _lerp(from_value.b, to_value.b, progress),
        _lerp(from_value.a, to_value.a, progress),
    )


def _lerp_corner_radius(
    from_value: CornerRadius,
    to_value: CornerRadius,
    progress: float,
) -> CornerRadius:
    return CornerRadius(
        _lerp(from_value.top_left, to_value.top_left, progress),
        _lerp(from_value.top_right, to_value.top_right, progress),
        _lerp(from_value.bottom_right, to_value.bottom_right, progress),
        _lerp(from_value.bottom_left, to_value.bottom_left, progress),
    )
