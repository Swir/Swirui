import pytest

from swirui.rendering import FrameScheduler


@pytest.mark.parametrize("target_fps", [60, 120, 144, 165, 240])
def test_frame_scheduler_supports_high_refresh_targets(target_fps: int) -> None:
    scheduler = FrameScheduler(target_fps=target_fps)
    interval = 1.0 / target_fps

    assert scheduler.frame_interval == pytest.approx(interval)
    assert scheduler.consume(0.0) is True
    scheduler.invalidate()
    assert scheduler.consume(interval * 0.99) is False
    assert scheduler.consume(interval) is True


def test_frame_scheduler_records_pacing_telemetry() -> None:
    scheduler = FrameScheduler(target_fps=120)
    interval = scheduler.frame_interval

    assert scheduler.consume(0.0) is True
    scheduler.invalidate()
    assert scheduler.consume(interval) is True

    stats = scheduler.stats
    assert stats.frame_number == 2
    assert stats.last_frame_delta == pytest.approx(interval)
    assert stats.instantaneous_fps == pytest.approx(120.0)
    assert stats.smoothed_fps == pytest.approx(120.0)
    assert stats.pacing_error == pytest.approx(0.0)

    scheduler.invalidate()
    assert scheduler.consume(interval * 2.25) is True
    assert stats.last_frame_delta == pytest.approx(interval * 1.25)
    assert stats.instantaneous_fps == pytest.approx(96.0)
    assert stats.smoothed_fps == pytest.approx(115.2)
    assert stats.pacing_error == pytest.approx(interval * 0.25)


def test_retargeting_scheduler_changes_deadline_without_resetting_stats() -> None:
    scheduler = FrameScheduler(target_fps=60)
    assert scheduler.consume(0.0) is True

    scheduler.target_fps = 144
    scheduler.invalidate()
    assert scheduler.frame_interval == pytest.approx(1 / 144)
    assert scheduler.consume((1 / 144) * 0.99) is False
    assert scheduler.consume(1 / 144) is True
    assert scheduler.stats.frame_number == 2
    assert scheduler.stats.instantaneous_fps == pytest.approx(144.0)
