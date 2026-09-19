from __future__ import annotations

import math
import sys
import time

import pytest

from swirui import App, RotateTransition, Widget, Window, linear, mount
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, Point, Rect, SceneNode, SceneNodeKind, WgpuRenderer


class _AffineTextTile(Widget):
    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.TEXT,
            bounds=self.bounds,
            opacity=self.opacity,
            fill=Color.from_hex("#62E5FF"),
            text="Affine Ω shaped text",
            font_size=28.0,
            clip_to_bounds=self.clip_to_bounds,
        )


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AffineText.{id(backend):x}"
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
            pytest.fail("Timed out waiting for affine-text GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="native text rasterizer requires Windows wheel")
def test_native_text_rasterizer_returns_rgba_pixels() -> None:
    import _swirui_native

    width = 192
    height = 64
    rgba = _swirui_native.rasterize_text_rgba(
        "SwirUI Ω",
        width,
        height,
        26.0,
        0.38,
        0.90,
        1.0,
        1.0,
        "Segoe UI",
    )
    rgba_bytes = bytes(rgba)
    assert len(rgba_bytes) == width * height * 4
    assert any(rgba_bytes[index] for index in range(3, len(rgba_bytes), 4))


@pytest.mark.skipif(sys.platform != "win32", reason="affine text smoke requires Windows")
def test_rotate_transition_renders_shaped_text_through_affine_image_pipeline() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI affine text smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI affine text", width=680, height=380))
    tile = _AffineTextTile(
        bounds=Rect(170.0, 135.0, 340.0, 72.0),
        key="affine-text-tile",
        clip_to_bounds=True,
    )
    runtime = mount(window, tile)

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        assert renderer.last_text_count == 1
        initial_contexts = renderer.persistent_context_count

        transition = RotateTransition(
            tile,
            math.pi / 3.0,
            duration=0.20,
            easing=linear,
        ).start()
        transition.advance(0.10)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)

        assert renderer.persistent_context_count == initial_contexts
        assert renderer.last_text_count == 0
        assert renderer.last_image_count > 0
        assert renderer.affine_text_cache_size == 1
        assert tile.visual_rotation == pytest.approx(math.pi / 6.0)
        assert runtime.generation >= 2
        assert window.scene is not None
        root = window.scene.root
        visual_center = root.transform.transform_point(Point(340.0, 171.0))
        assert window.scene.hit_test(visual_center) is root

        transition.advance(0.10)
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.affine_text_cache_size == 1
        assert renderer.last_image_count > 0
    finally:
        app.stop()
