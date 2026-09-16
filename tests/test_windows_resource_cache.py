from __future__ import annotations

import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Win32 GPU resource cache smoke requires Windows",
)
def test_real_wgpu_image_cache_skips_identical_texture_reupload() -> None:
    backend = Win32PlatformBackend()
    renderer = WgpuRenderer()
    first = bytes((20, 150, 255, 255))
    changed = bytes((255, 100, 40, 255))
    renderer.register_image_rgba("cached-pixel", 1, 1, first)

    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 360, 240))
    root.add(
        SceneNode(
            "image",
            SceneNodeKind.IMAGE,
            Rect(80, 50, 180, 120),
            resource_id="cached-pixel",
        )
    )
    window = Window(title="SwirUI GPU Resource Cache Smoke", width=360, height=240)
    window.set_scene(Scene(360, 240, root))
    app = App("SwirUI GPU Resource Cache Smoke", platform_backend=backend, renderer=renderer)
    app.add_window(window)

    try:
        app.start()
        assert window.native_handle is not None
        context = renderer._contexts[window.native_handle.value]
        assert renderer.last_image_count == 1
        assert renderer.image_resource_count == 1
        assert renderer.image_resource_bytes == 4
        assert renderer.image_native_uploads == 1
        assert renderer.image_cache_hits == 0
        assert context.image_resource_count == 1
        assert context.image_resource_size("cached-pixel") == (1, 1)

        renderer.register_image_rgba("cached-pixel", 1, 1, first)
        assert renderer.image_cache_hits == 1
        assert renderer.image_native_uploads == 1
        assert context.image_resource_count == 1

        renderer.register_image_rgba("cached-pixel", 1, 1, changed)
        assert renderer.image_cache_hits == 1
        assert renderer.image_native_uploads == 2
        assert context.image_resource_count == 1
        assert context.image_resource_size("cached-pixel") == (1, 1)

        renderer.render(window, None)
        assert renderer.last_image_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
