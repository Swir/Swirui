from __future__ import annotations

import math
import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    CornerRadius,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)
from swirui.rendering.affine import Affine2D


def _isolated_backend(label: str) -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AffinePathSmoke.{label}.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Affine GPU path smoke requires Windows")
def test_rotated_scenegraph_geometry_reaches_real_wgpu_and_keeps_input_aligned() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 560.0, 360.0),
        hit_testable=False,
    )
    path_node = SceneNode(
        key="rotated-path",
        kind=SceneNodeKind.PATH,
        bounds=Rect(70.0, 90.0, 180.0, 140.0),
        fill=Color.from_hex("#0088FF"),
        path=Path2D.polygon(
            Point(0.0, 0.0),
            Point(180.0, 0.0),
            Point(180.0, 140.0),
            Point(0.0, 140.0),
        ),
        transform=Affine2D.rotation(
            math.radians(24.0),
            origin=Point(160.0, 160.0),
        ),
    )
    rectangle_node = SceneNode(
        key="rotated-rounded-rectangle",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(330.0, 105.0, 140.0, 110.0),
        fill=Color.from_hex("#62E5FF"),
        corner_radius=CornerRadius(28.0, 20.0, 12.0, 6.0),
        transform=Affine2D.rotation(
            math.radians(-19.0),
            origin=Point(400.0, 160.0),
        ),
    )
    root.add(path_node, rectangle_node)
    scene = Scene(560.0, 360.0, root)

    renderer = WgpuRenderer()
    backend = _isolated_backend("scenegraph")
    app = App(
        "SwirUI Affine Geometry Integration",
        platform_backend=backend,
        renderer=renderer,
    )
    window = Window(title="SwirUI Affine Geometry", width=560, height=360)
    window.set_scene(scene)
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_path_count > 2
        assert renderer.last_rectangle_count == 0
        assert renderer.last_text_count == 0
        assert renderer.last_image_count == 0
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend

        authored_path_probe = Point(110.0, 125.0)
        visual_path_probe = path_node.transform.transform_point(authored_path_probe)
        assert scene.hit_test(visual_path_probe) is path_node

        authored_rectangle_probe = Point(390.0, 155.0)
        visual_rectangle_probe = rectangle_node.transform.transform_point(
            authored_rectangle_probe
        )
        assert scene.hit_test(visual_rectangle_probe) is rectangle_node

        path_node.transform = Affine2D.rotation(
            math.radians(-17.0),
            origin=Point(160.0, 160.0),
        )
        rectangle_node.transform = Affine2D.rotation(
            math.radians(14.0),
            origin=Point(400.0, 160.0),
        )
        scene.touch()
        renderer.render(window, None)

        assert renderer.frames_rendered == 2
        assert renderer.last_path_count > 2
        assert renderer.persistent_context_count == 1
        visual_path_probe = path_node.transform.transform_point(authored_path_probe)
        assert scene.hit_test(visual_path_probe) is path_node
        visual_rectangle_probe = rectangle_node.transform.transform_point(
            authored_rectangle_probe
        )
        assert scene.hit_test(visual_rectangle_probe) is rectangle_node
    finally:
        app.stop()
