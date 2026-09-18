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
    Label,
    RevealTransition,
    ScaleTransition,
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
def test_visual_transitions_reuse_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI visual transition smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI visual transition", width=640, height=360))
    root = Component("visual-transition-root")
    card = Card(key="transition-card", bounds=Rect(90.0, 70.0, 460.0, 220.0), opacity=0.8)
    label = Label(
        "GPU retained transition",
        key="transition-label",
        bounds=Rect(200.0, 140.0, 200.0, 40.0),
    )
    card.add(label)
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
    scale = ScaleTransition(card, from_scale=0.8, duration=0.30, easing=linear)
    reveal = RevealTransition(card, duration=0.30, easing=linear)
    transition = AnimationParallel(fade, slide, scale, reveal)

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
        assert card.visual_scale == pytest.approx(0.9)
        assert card.visual_clip == Rect(90.0, 70.0, 230.0, 220.0)
        assert transition.cancel() is True

        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
        assert window.scene is not None
        card_node = next(node for node in window.scene.walk() if node.key == "transition-card")
        label_node = next(node for node in window.scene.walk() if node.key == "transition-label")
        assert card_node.bounds == Rect(143.0, 81.0, 414.0, 198.0)
        assert card_node.clip_rect == Rect(143.0, 81.0, 207.0, 198.0)
        assert card_node.opacity == pytest.approx(0.4)
        assert label_node.bounds == Rect(242.0, 144.0, 180.0, 36.0)
        assert label_node.font_size == pytest.approx(label.font_size * 0.9)
        assert window.scene.hit_test_xy(500.0, 180.0) is None

        fade.restore()
        slide.restore()
        scale.restore()
        reveal.restore()
        assert card.opacity == pytest.approx(0.8)
        assert card.visual_offset == Point()
        assert card.visual_scale == pytest.approx(1.0)
        assert card.visual_clip is None
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        card_node = next(node for node in window.scene.walk() if node.key == "transition-card")
        assert card_node.bounds == Rect(90.0, 70.0, 460.0, 220.0)
        assert card_node.clip_rect is None
        assert card_node.opacity == pytest.approx(0.8)
    finally:
        controller.dispose()
        app.stop()
