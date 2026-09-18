from __future__ import annotations

import sys
import time

import pytest

from swirui import AnimationController, App, Button, ScaleTransition, Window, linear, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.ScaleAnimation.{id(backend):x}"
    return backend


def _render_after_invalidation(
    app: App,
    renderer: WgpuRenderer,
    previous_frames: int,
    *,
    timeout: float = 1.0,
) -> None:
    deadline = time.monotonic() + timeout
    while renderer.frames_rendered <= previous_frames:
        app.process_events()
        app.render_pending(time.monotonic() + 1.0)
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for visual-scale GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="visual-scale smoke requires Windows")
def test_scale_transition_reuses_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI scale smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI visual scale", width=640, height=360))
    button = Button(
        "GPU scale",
        key="scale-button",
        bounds=Rect(120.0, 110.0, 240.0, 72.0),
        corner_radius=16.0,
        font_size=24.0,
    )
    runtime = mount(window, button)
    controller = AnimationController(app, window)
    transition = ScaleTransition(button, 0.5, duration=0.30, easing=linear)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        authored_bounds = button.bounds

        controller.play(transition)
        controller.tick(0.15)
        assert button.visual_scale == pytest.approx(0.75)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
        assert window.scene is not None
        node = next(node for node in window.scene.walk() if node.key == "scale-button")
        text = next(node for node in window.scene.walk() if node.key == "scale-button:content")
        assert node.bounds == Rect(150.0, 119.0, 180.0, 54.0)
        assert node.corner_radius.top_left == pytest.approx(12.0)
        assert text.font_size == pytest.approx(18.0)
        assert button.bounds == authored_bounds

        controller.tick(0.15)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert button.visual_scale == pytest.approx(0.5)

        transition.restore()
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        node = next(node for node in window.scene.walk() if node.key == "scale-button")
        assert node.bounds == authored_bounds
    finally:
        controller.dispose()
        app.stop()
