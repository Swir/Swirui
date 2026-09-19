from __future__ import annotations

import math
import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Point, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer
from swirui.rendering.affine import Affine2D


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AffineImageClipSmoke.{id(backend):x}"
    return backend


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Exact affine image clipping smoke requires Windows",
)
def test_rotated_clip_submits_exact_image_triangles_to_real_wgpu() -> None:
    clip_group = SceneNode(
        key="rotated-image-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(85.0, 65.0, 230.0, 165.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(
            math.radians(17.0),
            origin=Point(200.0, 147.5),
        ),
    )
    image = SceneNode(
        key="clipped-image",
        kind=SceneNodeKind.IMAGE,
        bounds=Rect(45.0, 25.0, 310.0, 245.0),
        resource_id="clip-checker",
        opacity=0.9,
        transform=Affine2D.rotation(
            math.radians(-9.0),
            origin=Point(200.0, 147.5),
        ),
    )
    clip_group.add(image)
    scene = Scene(420.0, 300.0, clip_group)

    renderer = WgpuRenderer()
    renderer.register_image_rgba(
        "clip-checker",
        2,
        2,
        bytes(
            [
                0,
                136,
                255,
                255,
                98,
                229,
                255,
                255,
                98,
                229,
                255,
                255,
                0,
                136,
                255,
                255,
            ]
        ),
    )
    backend = _isolated_backend()
    app = App(
        "SwirUI Exact Affine Image Clip",
        platform_backend=backend,
        renderer=renderer,
    )
    window = Window(title="SwirUI Affine Image Clip", width=420, height=300)
    window.set_scene(scene)
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_image_count >= 2
        assert renderer.last_path_count == 0
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend

        authored_probe = Point(200.0, 147.5)
        image_world = image.transform.then(clip_group.transform)
        visual_probe = image_world.transform_point(authored_probe)
        assert scene.hit_test(visual_probe) is image

        clip_group.transform = Affine2D.rotation(
            math.radians(-13.0),
            origin=Point(200.0, 147.5),
        )
        image.transform = Affine2D.rotation(
            math.radians(14.0),
            origin=Point(200.0, 147.5),
        )
        scene.touch()
        renderer.render(window, None)

        assert renderer.frames_rendered == 2
        assert renderer.last_image_count >= 2
        image_world = image.transform.then(clip_group.transform)
        visual_probe = image_world.transform_point(authored_probe)
        assert scene.hit_test(visual_probe) is image
    finally:
        app.stop()
