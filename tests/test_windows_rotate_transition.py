from __future__ import annotations

import math
import sys
import time

import pytest

from swirui import App, RotateTransition, Widget, Window, linear, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Point, Rect, SceneNode, SceneNodeKind, WgpuRenderer


class _SolidTile(Widget):
    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            fill=Color(0.0, 0.53, 1.0, 1.0),
            clip_to_bounds=self.clip_to_bounds,
        )


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.RotateTransition.{id(backend):x}"
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
            pytest.fail("Timed out waiting for rotate-transition GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="rotate transition smoke requires Windows")
def test_rotate_transition_uses_persistent_native_affine_path_and_hit_testing() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI rotate transition smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI rotate transition", width=640, height=360))
    tile = _SolidTile(
        bounds=Rect(190.0, 130.0, 220.0, 84.0),
        key="rotate-native-tile",
    )
    runtime = mount(window, tile)
    authored_bounds = tile.bounds

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        initial_contexts = renderer.persistent_context_count

        transition = RotateTransition(
            tile,
            math.pi * 0.5,
            duration=0.20,
            easing=linear,
        ).start()
        transition.advance(0.10)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert renderer.last_path_count > 0
        assert tile.visual_rotation == pytest.approx(math.pi * 0.25)
        assert tile.bounds == authored_bounds
        assert runtime.generation >= 2
        assert window.scene is not None
        assert window.scene.has_affine_transforms is True

        root = window.scene.root
        authored_inside = Point(
            authored_bounds.x + 12.0,
            authored_bounds.y + 12.0,
        )
        visual_inside = root.transform.transform_point(authored_inside)
        assert window.scene.hit_test(visual_inside) is root

        transition.advance(0.10)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert tile.visual_rotation == pytest.approx(math.pi * 0.5)
        assert renderer.last_path_count > 0
    finally:
        app.stop()
