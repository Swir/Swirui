import time

import pytest

from swirui import (
    AdaptiveQualityController,
    AdaptiveQualityPolicy,
    App,
    AppConfig,
    Component,
    VisualQuality,
    Window,
)
from swirui.core import Event
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


class SlowNullRenderer(NullRenderer):
    """Deterministic test renderer that deliberately exceeds a 60 Hz frame budget."""

    def render(self, window: Window, root: Component | None) -> None:
        time.sleep(0.020)
        super().render(window, root)


def test_auto_quality_demotes_quickly_and_promotes_after_sustained_headroom() -> None:
    controller = AdaptiveQualityController(
        VisualQuality.AUTO,
        policy=AdaptiveQualityPolicy(
            initial_quality=VisualQuality.QUALITY,
            downgrade_frames=2,
            upgrade_frames=3,
            cooldown_frames=1,
        ),
    )

    assert controller.resolved_quality is VisualQuality.QUALITY
    assert controller.observe_frame(45.0, 60, render_duration_seconds=0.020) is None
    demotion = controller.observe_frame(45.0, 60, render_duration_seconds=0.020)

    assert demotion is not None
    assert demotion.old_quality is VisualQuality.QUALITY
    assert demotion.new_quality is VisualQuality.BALANCED
    assert demotion.reason == "sustained_frame_pressure"
    assert demotion.fps_ratio == pytest.approx(0.75)
    assert demotion.render_budget_utilization == pytest.approx(1.2)
    assert controller.stats.cooldown_remaining == 1

    assert controller.observe_frame(60.0, 60, render_duration_seconds=0.002) is None
    assert controller.stats.cooldown_remaining == 0
    assert controller.observe_frame(60.0, 60, render_duration_seconds=0.002) is None
    assert controller.observe_frame(60.0, 60, render_duration_seconds=0.002) is None
    promotion = controller.observe_frame(60.0, 60, render_duration_seconds=0.002)

    assert promotion is not None
    assert promotion.old_quality is VisualQuality.BALANCED
    assert promotion.new_quality is VisualQuality.QUALITY
    assert promotion.reason == "sustained_headroom"
    assert controller.stats.automatic_changes == 2


def test_auto_quality_hysteresis_clears_streaks_in_neutral_band() -> None:
    controller = AdaptiveQualityController(
        policy=AdaptiveQualityPolicy(
            initial_quality=VisualQuality.BALANCED,
            downgrade_fps_ratio=0.8,
            upgrade_fps_ratio=0.98,
            downgrade_frames=2,
            upgrade_frames=2,
            cooldown_frames=0,
        )
    )

    assert controller.observe_frame(45.0, 60, render_duration_seconds=0.020) is None
    assert controller.stats.below_budget_streak == 1
    assert controller.observe_frame(54.0, 60, render_duration_seconds=0.020) is None
    assert controller.stats.below_budget_streak == 0
    assert controller.stats.above_budget_streak == 0

    assert controller.observe_frame(60.0, 60, render_duration_seconds=0.002) is None
    assert controller.stats.above_budget_streak == 1
    assert controller.observe_frame(54.0, 60, render_duration_seconds=0.002) is None
    assert controller.stats.above_budget_streak == 0


def test_sparse_idle_frames_do_not_trigger_false_quality_demotions() -> None:
    controller = AdaptiveQualityController()

    for _ in range(30):
        assert controller.observe_frame(5.0, 60, render_duration_seconds=0.001) is None

    assert controller.resolved_quality is VisualQuality.BALANCED
    assert controller.stats.below_budget_streak == 0
    assert controller.stats.automatic_changes == 0
    assert controller.stats.last_render_budget_utilization == pytest.approx(0.06)


def test_fixed_quality_never_adapts_and_mode_switch_resets_auto_baseline() -> None:
    controller = AdaptiveQualityController(VisualQuality.CINEMATIC)

    for _ in range(30):
        assert controller.observe_frame(15.0, 60, render_duration_seconds=0.050) is None
    assert controller.resolved_quality is VisualQuality.CINEMATIC
    assert controller.stats.automatic_changes == 0

    old_quality, new_quality = controller.set_mode(VisualQuality.AUTO)
    assert old_quality is VisualQuality.CINEMATIC
    assert new_quality is VisualQuality.BALANCED
    assert controller.resolved_quality is VisualQuality.BALANCED
    assert controller.stats.below_budget_streak == 0
    assert controller.stats.cooldown_remaining == 0
    assert controller.stats.last_render_duration_seconds is None


def test_policy_and_samples_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="concrete"):
        AdaptiveQualityPolicy(initial_quality=VisualQuality.AUTO)
    with pytest.raises(ValueError, match="exceed"):
        AdaptiveQualityPolicy(downgrade_fps_ratio=0.9, upgrade_fps_ratio=0.8)
    with pytest.raises(ValueError, match="upgrade_render_budget_ratio"):
        AdaptiveQualityPolicy(
            downgrade_render_budget_ratio=0.5,
            upgrade_render_budget_ratio=0.6,
        )
    with pytest.raises(ValueError, match="positive"):
        AdaptiveQualityPolicy(downgrade_frames=0)

    controller = AdaptiveQualityController()
    with pytest.raises(ValueError, match="target_fps"):
        controller.observe_frame(60.0, 0, render_duration_seconds=0.001)
    with pytest.raises(ValueError, match="positive finite"):
        controller.observe_frame(float("nan"), 60, render_duration_seconds=0.001)
    with pytest.raises(ValueError, match="positive finite"):
        controller.observe_frame(0.0, 60, render_duration_seconds=0.001)
    with pytest.raises(ValueError, match="finite non-negative"):
        controller.observe_frame(60.0, 60, render_duration_seconds=-0.001)


def test_app_auto_quality_reacts_to_real_frame_pressure_and_emits_transition() -> None:
    renderer = SlowNullRenderer()
    app = App(
        config=AppConfig(visual_quality=VisualQuality.AUTO, target_fps=60),
        platform_backend=NullPlatformBackend(),
        renderer=renderer,
    )
    window = app.add_window(Window())
    quality_events: list[Event] = []
    frame_events: list[Event] = []
    app.on("visual_quality_changed", quality_events.append)
    app.on("frame_rendered", frame_events.append)

    app.start()
    assert app.effective_visual_quality is VisualQuality.BALANCED
    now = float(frame_events[-1].data["frame_time"])

    for _ in range(6):
        app.invalidate(window)
        now += 1.0 / 30.0
        assert app.render_pending(now) == 1

    assert app.effective_visual_quality is VisualQuality.PERFORMANCE
    assert len(quality_events) == 1
    change = quality_events[0].data
    assert change["old_quality"] is VisualQuality.BALANCED
    assert change["quality"] is VisualQuality.PERFORMANCE
    assert change["mode"] is VisualQuality.AUTO
    assert change["reason"] == "sustained_frame_pressure"
    assert change["smoothed_fps"] == pytest.approx(30.0)
    assert change["target_fps"] == 60
    assert float(change["render_duration_seconds"]) >= 0.020
    assert float(change["render_budget_utilization"]) >= 1.2
    assert app.quality_stats.automatic_changes == 1

    last_frame = frame_events[-1].data
    assert last_frame["visual_quality"] is VisualQuality.BALANCED
    assert last_frame["effective_visual_quality"] is VisualQuality.PERFORMANCE
    assert last_frame["configured_visual_quality"] is VisualQuality.AUTO
    assert float(last_frame["render_duration_seconds"]) >= 0.020
    assert float(last_frame["render_budget_utilization"]) >= 1.2

    app.stop()


def test_app_fixed_quality_disables_adaptation_and_direct_config_changes_are_synced() -> None:
    renderer = NullRenderer()
    app = App(
        config=AppConfig(visual_quality=VisualQuality.AUTO, target_fps=60),
        platform_backend=NullPlatformBackend(),
        renderer=renderer,
    )
    window = app.add_window(Window())
    quality_events: list[Event] = []
    frame_events: list[Event] = []
    app.on("visual_quality_changed", quality_events.append)
    app.on("frame_rendered", frame_events.append)
    app.start()

    app.set_visual_quality(VisualQuality.CINEMATIC)
    assert app.config.visual_quality is VisualQuality.CINEMATIC
    assert app.effective_visual_quality is VisualQuality.CINEMATIC
    assert quality_events[-1].data["reason"] == "configuration"

    now = float(frame_events[-1].data["frame_time"])
    for _ in range(12):
        app.invalidate(window)
        now += 1.0 / 20.0
        assert app.render_pending(now) == 1
    assert app.effective_visual_quality is VisualQuality.CINEMATIC

    app.config.visual_quality = VisualQuality.PERFORMANCE
    app.invalidate(window)
    now += 1.0 / 20.0
    assert app.render_pending(now) == 1
    assert app.effective_visual_quality is VisualQuality.PERFORMANCE
    assert quality_events[-1].data["old_mode"] is VisualQuality.CINEMATIC
    assert quality_events[-1].data["mode"] is VisualQuality.PERFORMANCE

    app.stop()
