"""Deterministic retained particle effects driven by the SwirUI animation clock."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from swirui.animation import AnimationStatus
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_DEFAULT_PARTICLE_COLOR = Color(0.18, 0.76, 1.0, 0.9)


@dataclass(frozen=True, slots=True)
class ParticleSample:
    """One immutable logical-DIP particle sample for diagnostics and tests."""

    x: float
    y: float
    size: float
    opacity: float
    color: Color


@dataclass(frozen=True, slots=True)
class _ParticleSpec:
    x: float
    y: float
    velocity_x: float
    velocity_y: float
    lifetime: float
    phase_or_delay: float
    size: float
    color: Color


class ParticleField(Widget):
    """GPU-batched retained particle field with frame-independent motion.

    Particle motion is sampled analytically from absolute elapsed time rather than
    integrated frame-by-frame. The same seed and elapsed time therefore produce the
    same geometry at 60, 120, 144 Hz or under irregular frame pacing. Every particle
    compiles to the existing rounded-rectangle GPU batch; no second renderer or image
    upload path is introduced.

    A looping field runs until cancelled unless ``duration`` is supplied. A non-looping
    field without an explicit duration completes after the final staggered particle
    lifetime. The object implements SwirUI's structural animation-playable contract and
    can be handed directly to :class:`swirui.AnimationController`.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        key: str | None = None,
        particle_count: int = 64,
        seed: int = 0,
        colors: Sequence[Color] | None = None,
        speed_range: tuple[float, float] = (18.0, 72.0),
        size_range: tuple[float, float] = (2.0, 6.0),
        lifetime_range: tuple[float, float] = (1.2, 3.4),
        direction_range_degrees: tuple[float, float] = (200.0, 340.0),
        gravity_y: float = 18.0,
        loop: bool = True,
        duration: float | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            raise ValueError("ParticleField bounds must have positive dimensions.")
        if not 1 <= int(particle_count) <= 4096:
            raise ValueError("particle_count must be between 1 and 4096.")
        palette = (_DEFAULT_PARTICLE_COLOR,) if colors is None else tuple(colors)
        if not palette:
            raise ValueError("ParticleField requires at least one color.")
        self._speed_range = self._validate_range(speed_range, "speed_range", allow_zero=True)
        self._size_range = self._validate_range(size_range, "size_range", allow_zero=False)
        self._lifetime_range = self._validate_range(
            lifetime_range,
            "lifetime_range",
            allow_zero=False,
        )
        self._direction_range = self._validate_finite_pair(
            direction_range_degrees,
            "direction_range_degrees",
        )
        self._gravity_y = self._finite_float("gravity_y", gravity_y)
        self._loop = bool(loop)
        self._on_complete = on_complete
        self._elapsed = 0.0
        self._status = AnimationStatus.IDLE
        self._seed = int(seed)
        self._particle_count = int(particle_count)
        self._specs = self._build_specs(self._particle_count, self._seed, palette)
        if duration is None:
            self._duration = (
                None
                if self._loop
                else max(spec.phase_or_delay + spec.lifetime for spec in self._specs)
            )
        else:
            normalized_duration = self._finite_float("duration", duration)
            if normalized_duration <= 0.0:
                raise ValueError("duration must be greater than zero when supplied.")
            self._duration = normalized_duration
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=False,
        )

    @property
    def status(self) -> AnimationStatus:
        return self._status

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def duration(self) -> float | None:
        return self._duration

    @property
    def particle_count(self) -> int:
        return self._particle_count

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def loop(self) -> bool:
        return self._loop

    def start(self) -> ParticleField:
        """Restart the deterministic field from elapsed time zero."""

        self._elapsed = 0.0
        self._status = AnimationStatus.RUNNING
        self.invalidate(reason="particle_animation_start")
        return self

    def advance(self, delta_seconds: float) -> float:
        """Advance by elapsed seconds and return unused tail after finite completion."""

        delta = self._finite_float("delta_seconds", delta_seconds)
        if delta < 0.0:
            raise ValueError("delta_seconds must be non-negative.")
        if self._status is not AnimationStatus.RUNNING:
            return delta
        if delta == 0.0:
            return 0.0

        duration = self._duration
        if duration is None:
            self._elapsed += delta
            self.invalidate(reason="particle_animation_frame")
            return 0.0

        remaining = max(0.0, duration - self._elapsed)
        consumed = min(delta, remaining)
        self._elapsed += consumed
        self.invalidate(reason="particle_animation_frame")
        if self._elapsed >= duration:
            self._elapsed = duration
            self._status = AnimationStatus.COMPLETED
            if self._on_complete is not None:
                self._on_complete()
        return max(0.0, delta - consumed)

    def cancel(self) -> bool:
        """Stop future motion while retaining the current visual sample."""

        if self._status in {AnimationStatus.CANCELLED, AnimationStatus.COMPLETED}:
            return False
        self._status = AnimationStatus.CANCELLED
        self.invalidate(reason="particle_animation_cancel")
        return True

    def samples(self) -> tuple[ParticleSample, ...]:
        """Return the currently visible deterministic particle samples."""

        samples: list[ParticleSample] = []
        width = self.bounds.width
        height = self.bounds.height
        for spec in self._specs:
            age = self._particle_age(spec)
            if age is None:
                continue
            x = spec.x * width + spec.velocity_x * age
            y = spec.y * height + spec.velocity_y * age + 0.5 * self._gravity_y * age * age
            if self._loop:
                x %= width
                y %= height
            fade_window = max(spec.lifetime * 0.18, 1e-9)
            fade_in = min(1.0, age / fade_window)
            fade_out = min(1.0, max(0.0, spec.lifetime - age) / fade_window)
            particle_opacity = max(0.0, min(fade_in, fade_out))
            if particle_opacity <= 0.0:
                continue
            samples.append(
                ParticleSample(
                    x=self.bounds.x + x,
                    y=self.bounds.y + y,
                    size=spec.size,
                    opacity=particle_opacity,
                    color=spec.color,
                )
            )
        return tuple(samples)

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=True,
            hit_testable=False,
        )
        for index, sample in enumerate(self.samples()):
            alpha = sample.color.a * sample.opacity
            root.add(
                SceneNode(
                    key=f"{self.key}:particle:{index}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(sample.x, sample.y, sample.size, sample.size),
                    fill=Color(sample.color.r, sample.color.g, sample.color.b, alpha),
                    corner_radius=CornerRadius.uniform(sample.size * 0.5),
                    hit_testable=False,
                )
            )
        return root

    def _particle_age(self, spec: _ParticleSpec) -> float | None:
        if self._loop:
            return (self._elapsed + spec.phase_or_delay) % spec.lifetime
        age = self._elapsed - spec.phase_or_delay
        if age < 0.0 or age >= spec.lifetime:
            return None
        return age

    def _build_specs(
        self,
        count: int,
        seed: int,
        palette: tuple[Color, ...],
    ) -> tuple[_ParticleSpec, ...]:
        rng = random.Random(seed)
        specs: list[_ParticleSpec] = []
        for _ in range(count):
            lifetime = rng.uniform(*self._lifetime_range)
            angle = math.radians(rng.uniform(*self._direction_range))
            speed = rng.uniform(*self._speed_range)
            specs.append(
                _ParticleSpec(
                    x=rng.random(),
                    y=rng.random(),
                    velocity_x=math.cos(angle) * speed,
                    velocity_y=math.sin(angle) * speed,
                    lifetime=lifetime,
                    phase_or_delay=rng.uniform(0.0, lifetime),
                    size=rng.uniform(*self._size_range),
                    color=palette[rng.randrange(len(palette))],
                )
            )
        return tuple(specs)

    @classmethod
    def _validate_range(
        cls,
        value: tuple[float, float],
        name: str,
        *,
        allow_zero: bool,
    ) -> tuple[float, float]:
        lower, upper = cls._validate_finite_pair(value, name)
        if lower < 0.0 or (not allow_zero and lower == 0.0):
            requirement = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{name} values must be {requirement}.")
        if upper < lower:
            raise ValueError(f"{name} upper bound cannot be smaller than the lower bound.")
        return lower, upper

    @classmethod
    def _validate_finite_pair(
        cls,
        value: tuple[float, float],
        name: str,
    ) -> tuple[float, float]:
        if len(value) != 2:
            raise ValueError(f"{name} must contain exactly two values.")
        return cls._finite_float(f"{name}[0]", value[0]), cls._finite_float(
            f"{name}[1]",
            value[1],
        )

    @staticmethod
    def _finite_float(name: str, value: float) -> float:
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite.")
        return normalized
