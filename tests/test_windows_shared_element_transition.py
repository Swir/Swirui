from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    AnimationController,
    App,
    Card,
    Component,
    SharedElementTransition,
    Window,
    linear,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.SharedElementTransition.{id(backend):x}"
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
            pytest.fail("Timed out waiting for shared-element GPU frame.")
        time.sleep(0.005)


def _center(bounds: Rect) -> tuple[float, float]:
    return (bounds.x + bounds.width * 0.5, bounds.y + bounds.height * 0.5)


@pytest.mark.skipif(sys.platform != "win32", reason="shared-element smoke requires Windows")
def test_shared_element_transition_reuses_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI shared-element smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI shared element", width=720, height=420))
    root = Component("shared-element-root")
    source = Card(key="shared-source", bounds=Rect(80.0, 90.0, 180.0, 120.0))
    target = Card(key="shared-target", bounds=Rect(380.0, 150.0, 200.0, 140.0))
    root.add(source, target)
    runtime = mount(window, root)
    controller = AnimationController(app, window)
    transition = SharedElementTransition(source, target, duration=0.30, easing=linear)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        controller.play(transition)
        controller.tick(0.15)
        assert source.opacity == pytest.approx(0.5)
        assert target.opacity == pytest.approx(0.5)

        assert transition.cancel() is True
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
        assert window.scene is not None
        source_node = next(node for node in window.scene.walk() if node.key == "shared-source")
        target_node = next(node for node in window.scene.walk() if node.key == "shared-target")
        assert _center(source_node.bounds) == pytest.approx(_center(target_node.bounds))
        assert source_node.opacity == pytest.approx(0.5)
        assert target_node.opacity == pytest.approx(0.5)

        transition.restore()
        controller.play(transition)
        controller.tick(0.30)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        target_node = next(node for node in window.scene.walk() if node.key == "shared-target")
        assert target_node.bounds == Rect(380.0, 150.0, 200.0, 140.0)
        assert target_node.opacity == pytest.approx(1.0)
    finally:
        controller.dispose()
        app.stop()
