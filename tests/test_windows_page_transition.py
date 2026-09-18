from __future__ import annotations

import sys
import time

import pytest

from swirui import (
    AnimationController,
    App,
    Card,
    Component,
    PageTransition,
    PageTransitionDirection,
    Window,
    linear,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.PageTransition.{id(backend):x}"
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
            pytest.fail("Timed out waiting for page-transition GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="page transition smoke requires Windows")
def test_page_transition_moves_retained_pages_without_recreating_wgpu_context() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI page transition smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI page transition", width=640, height=360))
    root = Component("page-transition-root")
    outgoing = Card(key="page-outgoing", bounds=Rect(90.0, 70.0, 460.0, 220.0))
    incoming = Card(key="page-incoming", bounds=Rect(90.0, 70.0, 460.0, 220.0))
    root.add(outgoing, incoming)
    runtime = mount(window, root)
    controller = AnimationController(app, window)
    transition = PageTransition(
        outgoing,
        incoming,
        duration=0.30,
        distance=48.0,
        direction=PageTransitionDirection.LEFT,
        easing=linear,
    )

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        controller.play(transition)
        controller.tick(0.15)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert runtime.generation > 1
        assert window.scene is not None
        outgoing_node = next(node for node in window.scene.walk() if node.key == "page-outgoing")
        incoming_node = next(node for node in window.scene.walk() if node.key == "page-incoming")
        assert outgoing_node.bounds.x == pytest.approx(66.0)
        assert incoming_node.bounds.x == pytest.approx(114.0)
        assert outgoing_node.opacity == pytest.approx(0.5)
        assert incoming_node.opacity == pytest.approx(0.5)

        controller.tick(0.15)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert window.scene is not None
        incoming_node = next(node for node in window.scene.walk() if node.key == "page-incoming")
        assert incoming_node.bounds.x == pytest.approx(90.0)
        assert incoming_node.opacity == pytest.approx(1.0)
    finally:
        controller.dispose()
        app.stop()
