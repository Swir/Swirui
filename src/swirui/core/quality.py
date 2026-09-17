"""Runtime visual-quality adaptation driven by frame pacing telemetry.

SwirUI keeps visual quality explicit: fixed profiles never change behind an
application's back, while ``VisualQuality.AUTO`` resolves to one of the concrete
Performance/Balanced/Quality/Ultra/Cinematic profiles. The controller uses
hysteresis, asymmetric promotion/demotion windows and a post-change cooldown so
brief frame-time spikes cannot make effects visibly oscillate between profiles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import VisualQuality

_CONCRETE_QUALITY_LEVELS = (
    VisualQuality.PERFORMANCE,
    VisualQuality.BALANCED,
    VisualQuality.QUALITY,
    VisualQuality.ULTRA,
    VisualQuality.CINEMATIC,
)


@dataclass(frozen=True, slots=True)
class AdaptiveQualityPolicy:
    """Deterministic thresholds used by :class:`AdaptiveQualityController`.

    Downgrades intentionally happen much faster than upgrades: preserving frame
    pacing is more important than immediately recovering visual detail after a
    transiently expensive scene. Ratios are relative to each window's effective
    target FPS, so the same policy works on 60, 120 and 144+ Hz displays.
    """

    initial_quality: VisualQuality = VisualQuality.BALANCED
    downgrade_fps_ratio: float = 0.88
    upgrade_fps_ratio: float = 0.985
    downgrade_frames: int = 6
    upgrade_frames: int = 180
    cooldown_frames: int = 45

    def __post_init__(self) -> None:
        if self.initial_quality not in _CONCRETE_QUALITY_LEVELS:
            raise ValueError("initial_quality must be a concrete visual-quality profile.")
        if not 0.0 < self.downgrade_fps_ratio < 1.0:
            raise ValueError("downgrade_fps_ratio must be between 0 and 1.")
        if not 0.0 < self.upgrade_fps_ratio <= 1.0:
            raise ValueError("upgrade_fps_ratio must be in the range (0, 1].")
        if self.upgrade_fps_ratio <= self.downgrade_fps_ratio:
            raise ValueError("upgrade_fps_ratio must exceed downgrade_fps_ratio.")
        if self.downgrade_frames <= 0:
            raise ValueError("downgrade_frames must be positive.")
        if self.upgrade_frames <= 0:
            raise ValueError("upgrade_frames must be positive.")
        if self.cooldown_frames < 0:
            raise ValueError("cooldown_frames cannot be negative.")


@dataclass(frozen=True, slots=True)
class AdaptiveQualityDecision:
    """One automatic profile transition produced by sustained frame telemetry."""

    old_quality: VisualQuality
    new_quality: VisualQuality
    reason: str
    smoothed_fps: float
    target_fps: int

    @property
    def fps_ratio(self) -> float:
        return self.smoothed_fps / self.target_fps


@dataclass(frozen=True, slots=True)
class AdaptiveQualityStats:
    """Immutable telemetry snapshot for debugging adaptive-quality behavior."""

    mode: VisualQuality
    resolved_quality: VisualQuality
    observed_frames: int
    automatic_changes: int
    below_budget_streak: int
    above_budget_streak: int
    cooldown_remaining: int
    last_smoothed_fps: float | None
    last_target_fps: int | None


class AdaptiveQualityController:
    """Resolve ``AUTO`` quality using stable frame-pacing feedback.

    Fixed quality modes are pass-through and never adapt. ``AUTO`` starts from
    ``policy.initial_quality`` and steps only one adjacent profile at a time.
    Sustained under-budget pacing demotes quickly; sustained headroom promotes
    slowly. A neutral hysteresis band clears both streaks.
    """

    def __init__(
        self,
        mode: VisualQuality = VisualQuality.AUTO,
        *,
        policy: AdaptiveQualityPolicy | None = None,
    ) -> None:
        self._policy = policy or AdaptiveQualityPolicy()
        self._mode = VisualQuality(mode)
        self._resolved_quality = self._resolve_initial(self._mode)
        self._observed_frames = 0
        self._automatic_changes = 0
        self._below_budget_streak = 0
        self._above_budget_streak = 0
        self._cooldown_remaining = 0
        self._last_smoothed_fps: float | None = None
        self._last_target_fps: int | None = None

    @property
    def mode(self) -> VisualQuality:
        return self._mode

    @property
    def resolved_quality(self) -> VisualQuality:
        return self._resolved_quality

    @property
    def policy(self) -> AdaptiveQualityPolicy:
        return self._policy

    @property
    def stats(self) -> AdaptiveQualityStats:
        return AdaptiveQualityStats(
            mode=self._mode,
            resolved_quality=self._resolved_quality,
            observed_frames=self._observed_frames,
            automatic_changes=self._automatic_changes,
            below_budget_streak=self._below_budget_streak,
            above_budget_streak=self._above_budget_streak,
            cooldown_remaining=self._cooldown_remaining,
            last_smoothed_fps=self._last_smoothed_fps,
            last_target_fps=self._last_target_fps,
        )

    def set_mode(self, mode: VisualQuality) -> tuple[VisualQuality, VisualQuality]:
        """Switch fixed/AUTO policy and return ``(old, new)`` resolved profiles."""

        normalized = VisualQuality(mode)
        old_quality = self._resolved_quality
        self._mode = normalized
        self._resolved_quality = self._resolve_initial(normalized)
        self._below_budget_streak = 0
        self._above_budget_streak = 0
        self._cooldown_remaining = 0
        self._last_smoothed_fps = None
        self._last_target_fps = None
        return old_quality, self._resolved_quality

    def observe_frame(
        self,
        smoothed_fps: float | None,
        target_fps: int,
    ) -> AdaptiveQualityDecision | None:
        """Consume one paced-frame sample and possibly step the AUTO profile."""

        if target_fps <= 0:
            raise ValueError("target_fps must be positive.")
        if smoothed_fps is None:
            return None
        if not math.isfinite(smoothed_fps) or smoothed_fps <= 0.0:
            raise ValueError("smoothed_fps must be a positive finite number when provided.")

        self._observed_frames += 1
        self._last_smoothed_fps = float(smoothed_fps)
        self._last_target_fps = int(target_fps)

        if self._mode is not VisualQuality.AUTO:
            return None

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            self._below_budget_streak = 0
            self._above_budget_streak = 0
            return None

        fps_ratio = smoothed_fps / target_fps
        if fps_ratio < self._policy.downgrade_fps_ratio:
            self._below_budget_streak += 1
            self._above_budget_streak = 0
            if self._below_budget_streak >= self._policy.downgrade_frames:
                return self._step_quality(
                    direction=-1,
                    reason="sustained_under_budget",
                    smoothed_fps=smoothed_fps,
                    target_fps=target_fps,
                )
            return None

        if fps_ratio >= self._policy.upgrade_fps_ratio:
            self._above_budget_streak += 1
            self._below_budget_streak = 0
            if self._above_budget_streak >= self._policy.upgrade_frames:
                return self._step_quality(
                    direction=1,
                    reason="sustained_headroom",
                    smoothed_fps=smoothed_fps,
                    target_fps=target_fps,
                )
            return None

        self._below_budget_streak = 0
        self._above_budget_streak = 0
        return None

    def _resolve_initial(self, mode: VisualQuality) -> VisualQuality:
        return self._policy.initial_quality if mode is VisualQuality.AUTO else mode

    def _step_quality(
        self,
        *,
        direction: int,
        reason: str,
        smoothed_fps: float,
        target_fps: int,
    ) -> AdaptiveQualityDecision | None:
        current_index = _CONCRETE_QUALITY_LEVELS.index(self._resolved_quality)
        next_index = min(
            len(_CONCRETE_QUALITY_LEVELS) - 1,
            max(0, current_index + direction),
        )
        self._below_budget_streak = 0
        self._above_budget_streak = 0
        if next_index == current_index:
            return None

        old_quality = self._resolved_quality
        self._resolved_quality = _CONCRETE_QUALITY_LEVELS[next_index]
        self._automatic_changes += 1
        self._cooldown_remaining = self._policy.cooldown_frames
        return AdaptiveQualityDecision(
            old_quality=old_quality,
            new_quality=self._resolved_quality,
            reason=reason,
            smoothed_fps=float(smoothed_fps),
            target_fps=int(target_fps),
        )
