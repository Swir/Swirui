import time

import pytest

from swirui import App, AppConfig, Component, Window
from swirui.core import Event
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


def test_app_creates_surface_and_renders_initial_frame() -> None:
    renderer = NullRenderer()
    app = App(
        "Render Runtime",
        config=AppConfig(target_fps=120),
        platform_backend=NullPlatformBackend(),
        renderer=renderer,
    )
    window = app.add_window(Window(width=800, height=600))

    app.start()

    assert window.native_handle is not None
    surface = renderer.surfaces[window.native_handle.value]
    assert (surface.width, surface.height) == (800, 600)
    assert renderer.frames_rendered == 1

    window.resize(1000, 700)
    assert (surface.width, surface.height) == (1000, 700)
    assert surface.generation == 1

    window.set_root(Component("dashboard"))
    frames = app.render_pending(time.monotonic() + 1.0)
    assert frames == 1
    assert renderer.frames_rendered == 2

    app.stop()
    assert surface.alive is False


def test_clean_window_does_not_render_repeatedly() -> None:
    renderer = NullRenderer()
    app = App(
        platform_backend=NullPlatformBackend(),
        renderer=renderer,
    )
    app.add_window(Window())
    app.start()

    initial_frames = renderer.frames_rendered
    assert app.render_pending(time.monotonic() + 10.0) == 0
    assert renderer.frames_rendered == initial_frames

    app.stop()


def test_frame_rendered_event_exposes_runtime_pacing_telemetry() -> None:
    renderer = NullRenderer()
    app = App(
        config=AppConfig(target_fps=120),
        platform_backend=NullPlatformBackend(),
        renderer=renderer,
    )
    window = app.add_window(Window())
    frame_events: list[Event] = []
    app.on("frame_rendered", frame_events.append)

    app.start()

    assert len(frame_events) == 1
    first_time = frame_events[0].data["frame_time"]
    assert isinstance(first_time, float)
    assert frame_events[0].data["frame_delta"] is None
    assert frame_events[0].data["instantaneous_fps"] is None
    assert frame_events[0].data["smoothed_fps"] is None
    assert frame_events[0].data["pacing_error"] is None

    window.set_root(Component("telemetry"))
    assert app.render_pending(first_time + (1 / 120)) == 1

    assert len(frame_events) == 2
    second = frame_events[1].data
    assert second["frame_number"] == 2
    assert second["frame_delta"] == pytest.approx(1 / 120)
    assert second["instantaneous_fps"] == pytest.approx(120.0)
    assert second["smoothed_fps"] == pytest.approx(120.0)
    assert second["pacing_error"] == pytest.approx(0.0)

    app.stop()
