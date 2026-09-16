import time

from swirui import App, AppConfig, Component, Window
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
