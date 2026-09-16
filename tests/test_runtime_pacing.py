import pytest

from swirui import App, AppConfig, Component, Window
from swirui.core import Event
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


def _running_app(target_fps: int = 60) -> tuple[App, Window, NullRenderer]:
    renderer = NullRenderer()
    app = App(
        config=AppConfig(target_fps=target_fps),
        platform_backend=NullPlatformBackend(),
        renderer=renderer,
    )
    window = app.add_window(Window())
    app.start()
    return app, window, renderer


def test_runtime_target_fps_retargets_existing_and_future_windows() -> None:
    app, first, _renderer = _running_app(60)
    changes: list[tuple[int, int]] = []
    app.on(
        "target_fps_changed",
        lambda event: changes.append(
            (event.data["old_target_fps"], event.data["target_fps"])
        ),
    )

    first_scheduler = app._frame_schedulers[first]
    assert first_scheduler.target_fps == 60

    app.set_target_fps(144)

    assert app.config.target_fps == 144
    assert first_scheduler.target_fps == 144
    assert first_scheduler.frame_interval == pytest.approx(1 / 144)
    assert changes == [(60, 144)]

    second = app.add_window(Window(title="144 Hz sibling"))
    assert app._frame_schedulers[second].target_fps == 144

    app.set_target_fps(144)
    assert changes == [(60, 144)]

    with pytest.raises(ValueError, match="target_fps"):
        app.set_target_fps(0)

    app.stop()


def test_next_frame_deadline_drives_sub_poll_interval_idle_sleep() -> None:
    app, window, _renderer = _running_app(144)
    scheduler = app._frame_schedulers[window]
    last_frame_time = scheduler.stats.last_frame_time
    assert last_frame_time is not None
    assert app.seconds_until_next_frame(last_frame_time) is None

    window.set_root(Component("animated"))
    interval = scheduler.frame_interval

    assert app.seconds_until_next_frame(last_frame_time) == pytest.approx(interval)
    assert app._idle_sleep_seconds(last_frame_time) == pytest.approx(0.004)

    almost_due = last_frame_time + interval - 0.001
    assert app.seconds_until_next_frame(almost_due) == pytest.approx(0.001)
    assert app._idle_sleep_seconds(almost_due) == pytest.approx(0.001)

    due = last_frame_time + interval + 1e-9
    assert app.seconds_until_next_frame(due) == pytest.approx(0.0)
    assert app._idle_sleep_seconds(due) == pytest.approx(0.0)

    app.stop()


def test_frame_event_reports_active_target_and_interval_after_retarget() -> None:
    app, window, _renderer = _running_app(60)
    events: list[Event] = []
    app.on("frame_rendered", events.append)
    app.set_target_fps(120)

    scheduler = app._frame_schedulers[window]
    last_frame_time = scheduler.stats.last_frame_time
    assert last_frame_time is not None
    window.set_root(Component("telemetry"))
    due = last_frame_time + scheduler.frame_interval + 1e-9
    assert app.render_pending(due) == 1

    assert len(events) == 1
    event = events[0]
    assert event.data["target_fps"] == 120
    assert event.data["frame_interval"] == pytest.approx(1 / 120)

    app.stop()
