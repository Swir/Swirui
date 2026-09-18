from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    App,
    Button,
    Component,
    FlipTransition,
    MorphTransition,
    RevealTransition,
    Window,
    linear,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AdvancedTransform.{id(backend):x}"
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
            pytest.fail("Timed out waiting for advanced-transform GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="advanced transform smoke requires Windows")
def test_morph_flip_reveal_reuse_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI advanced transform smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI morph flip reveal", width=760, height=420))

    root = Component("advanced-transform-root")
    source = Button(
        "Front",
        key="transform-source",
        bounds=Rect(90.0, 150.0, 180.0, 72.0),
        corner_radius=16.0,
        font_size=22.0,
    )
    target = Button(
        "Target",
        key="transform-target",
        bounds=Rect(430.0, 132.0, 270.0, 108.0),
        corner_radius=20.0,
        font_size=22.0,
    )
    root.add(source, target)
    runtime = mount(window, root)
    midpoint_calls = 0

    def swap_face() -> None:
        nonlocal midpoint_calls
        midpoint_calls += 1
        source.text = "Back"

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count
        source_bounds = source.bounds
        target_bounds = target.bounds

        reveal = RevealTransition(
            source,
            from_scale=0.8,
            duration=0.20,
            easing=linear,
        ).start()
        reveal.advance(0.10)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert source.visual_scale == pytest.approx(0.9)
        assert source.opacity == pytest.approx(0.5)

        reveal.advance(0.10)
        flip = FlipTransition(
            source,
            duration=0.20,
            easing=linear,
            on_midpoint=swap_face,
        ).start()
        flip.advance(0.10)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert midpoint_calls == 1
        assert source.visual_scale == pytest.approx(0.0)
        assert source.text == "Back"

        flip.advance(0.10)
        morph = MorphTransition(source, target, duration=0.30, easing=linear).start()
        morph.advance(0.15)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 3
        assert source.visual_scale == pytest.approx(1.25)
        assert target.visual_scale == pytest.approx(5.0 / 6.0)
        assert source.opacity == pytest.approx(0.5)
        assert target.opacity == pytest.approx(0.5)
        assert source.bounds == source_bounds
        assert target.bounds == target_bounds

        assert window.scene is not None
        source_node = next(node for node in window.scene.walk() if node.key == "transform-source")
        target_node = next(node for node in window.scene.walk() if node.key == "transform-target")
        assert source_node.bounds.width == pytest.approx(225.0)
        assert target_node.bounds.width == pytest.approx(225.0)

        morph.advance(0.15)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert source.visual_scale == pytest.approx(1.5)
        assert target.visual_scale == pytest.approx(1.0)
        assert source.opacity == pytest.approx(0.0)
        assert target.opacity == pytest.approx(1.0)
    finally:
        app.stop()
