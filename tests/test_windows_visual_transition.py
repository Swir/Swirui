from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    AnimationController,
    AnimationParallel,
    App,
    Card,
    Component,
    FadeTransition,
    SlideTransition,
    Window,
    linear,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Point, Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.VisualTransition.{id(backend):x}"
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
            pytest.fail("Timed out waiting for visual-transition GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="visual transition smoke requires Windows")
def test_fade_slide_transition_reuses_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI visual transition smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI visual transition", width=640, height=360))
    root = Component("visual-transition-root")
    card = Card(key="transition-card", bounds=Rect(90.0, 70.0, 460.0, 220.0), opacity=0.8)
    root.add(card)
    runtime = mount(window, root)
    controller = AnimationController(app, window)
    fade = FadeTransition(card, from_opacity=0.0, duration=0.30, easing=linear)
    slide = SlideTransition(
        card,
        from_offset=Point(60.0, 0.0),
        duration=0.30,
        easing=linear,
    )
    transition = AnimationParallel(fade, slide)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        controller.play(transition)
        controller.tick(0.15)
        assert card.opacity == pytest.approx(0.4)
        assert card.visual_offset.x == pytest.approx(30.0)
        assert transition.cancel() is True

        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
        assert window.scene is not None
        card_node = next(node for node in window.scene.walk() if node.key == "transition-card")
        assert card_node.bounds.x == pytest.approx(120.0)
        assert card_node.opacity == pytest.approx(0.4)

        fade.restore()
        slide.restore()
        assert card.opacity == pytest.approx(0.8)
        assert card.visual_offset == Point()
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        card_node = next(node for node in window.scene.walk() if node.key == "transition-card")
        assert card_node.bounds.x == pytest.approx(90.0)
        assert card_node.opacity == pytest.approx(0.8)
    finally:
        controller.dispose()
        app.stop()
