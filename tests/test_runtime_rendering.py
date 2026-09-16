import time

import pytest

from swirui import App, AppConfig, Component, Window
from swirui.core import Event
from swirui.platforms import (
    DisplayInfo,
    NativeWindowHandle,
    NullPlatformBackend,
    PlatformEvent,
    PlatformEventKind,
)
from swirui.rendering import NullRenderer


class DisplayAwareBackend(NullPlatformBackend):
    def __init__(self, display: DisplayInfo) -> None:
        super().__init__()
        self.current_display = display

    def displays(self) -> tuple[DisplayInfo, ...]:
        return (self.current_display,)

    def window_display(self, handle: NativeWindowHandle) -> DisplayInfo | None:
        self._require_window(handle)
        return self.current_display


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
    assert frame_events[0].data["target_fps"] == 120
    assert frame_events[0].data["configured_target_fps"] == 120
    assert frame_events[0].data["display_refresh_rate_hz"] is None
    assert frame_events[0].data["frame_delta"] is None
    assert frame_events[0].data["instantaneous_fps"] is None
    assert frame_events[0].data["smoothed_fps"] is None
    assert frame_events[0].data["pacing_error"] is None

    window.set_root(Component("telemetry"))
    expected_delta = (1 / 120) + 1e-6
    assert app.render_pending(first_time + expected_delta) == 1

    assert len(frame_events) == 2
    second = frame_events[1].data
    assert second["frame_number"] == 2
    assert second["frame_delta"] == pytest.approx(expected_delta)
    expected_fps = 1 / expected_delta
    assert second["instantaneous_fps"] == pytest.approx(expected_fps)
    assert second["smoothed_fps"] == pytest.approx(expected_fps)
    assert second["pacing_error"] == pytest.approx(1e-6)

    app.stop()


def test_window_frame_pacing_tracks_active_display_refresh_rate() -> None:
    display_60 = DisplayInfo("Display-60", 1920, 1080, refresh_rate_hz=60.0, primary=True)
    display_144 = DisplayInfo("Display-144", 2560, 1440, refresh_rate_hz=144.0)
    backend = DisplayAwareBackend(display_60)
    renderer = NullRenderer()
    app = App(
        config=AppConfig(target_fps=240),
        platform_backend=backend,
        renderer=renderer,
    )
    window = app.add_window(Window())
    retarget_events: list[Event] = []
    app.on("window_target_fps_changed", retarget_events.append)

    app.start()

    assert window.display == display_60
    assert app.window_target_fps(window) == 60

    assert window.native_handle is not None
    backend.current_display = display_144
    backend.post_event(PlatformEvent(PlatformEventKind.DISPLAY_CHANGED, window.native_handle))
    app.process_events()

    assert window.display == display_144
    assert app.window_target_fps(window) == 144
    assert len(retarget_events) == 1
    assert retarget_events[0].data["old_target_fps"] == 60
    assert retarget_events[0].data["target_fps"] == 144
    assert retarget_events[0].data["configured_target_fps"] == 240
    assert retarget_events[0].data["display"] == display_144

    app.set_target_fps(120)
    assert app.window_target_fps(window) == 120

    app.set_target_fps(300)
    assert app.window_target_fps(window) == 144

    app.stop()
