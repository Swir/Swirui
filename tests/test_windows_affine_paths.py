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
        bounds=Rect(0.0, 0.0, 620.0, 400.0),
        hit_testable=False,
    )
    path_node = SceneNode(
        key="rotated-path",
        kind=SceneNodeKind.PATH,
        bounds=Rect(55.0, 95.0, 170.0, 130.0),
        fill=Color.from_hex("#0088FF"),
        path=Path2D.polygon(
            Point(0.0, 0.0),
            Point(170.0, 0.0),
            Point(170.0, 130.0),
            Point(0.0, 130.0),
        ),
        transform=Affine2D.rotation(
            math.radians(24.0),
            origin=Point(140.0, 160.0),
        ),
    )
    rectangle_node = SceneNode(
        key="rotated-rounded-rectangle",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(255.0, 105.0, 130.0, 105.0),
        fill=Color.from_hex("#62E5FF"),
        corner_radius=CornerRadius(28.0, 20.0, 12.0, 6.0),
        transform=Affine2D.rotation(
            math.radians(-19.0),
            origin=Point(320.0, 158.0),
        ),
    )
    image_node = SceneNode(
        key="rotated-image",
        kind=SceneNodeKind.IMAGE,
        bounds=Rect(440.0, 105.0, 110.0, 110.0),
        resource_id="affine-checker",
        opacity=0.9,
        transform=Affine2D.rotation(
            math.radians(17.0),
            origin=Point(495.0, 160.0),
        ),
    )
    text_node = SceneNode(
        key="scaled-text",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(175.0, 285.0, 270.0, 50.0),
        text="SwirUI affine shaped text",
        fill=Color.from_hex("#EAF7FF"),
        font_size=24.0,
        transform=Affine2D.uniform_scale(
            1.12,
            origin=Point(310.0, 310.0),
        ).then(Affine2D.translation(8.0, -4.0)),
    )
    clip_group = SceneNode(
        key="rotated-geometry-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(20.0, 245.0, 135.0, 115.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(
            math.radians(11.0),
            origin=Point(87.5, 302.5),
        ),
    )
    clipped_path = SceneNode(
        key="exact-clipped-path",
        kind=SceneNodeKind.PATH,
        bounds=Rect(-5.0, 230.0, 190.0, 150.0),
        fill=Color.from_hex("#4DCBFF"),
        path=Path2D.polygon(
            Point(0.0, 0.0),
            Point(190.0, 15.0),
            Point(165.0, 150.0),
            Point(20.0, 135.0),
        ),
    )
    clip_group.add(clipped_path)
    root.add(path_node, rectangle_node, image_node, text_node, clip_group)
    scene = Scene(620.0, 400.0, root)

    renderer = WgpuRenderer()
    renderer.register_image_rgba(
        "affine-checker",
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
    backend = _isolated_backend("scenegraph")
    app = App(
        "SwirUI Affine Geometry Integration",
        platform_backend=backend,
        renderer=renderer,
    )
    window = Window(title="SwirUI Affine Geometry", width=620, height=400)
    window.set_scene(scene)
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_path_count > 4
        assert renderer.last_rectangle_count == 0
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 1
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend

        authored_path_probe = Point(105.0, 130.0)
        visual_path_probe = path_node.transform.transform_point(authored_path_probe)
        assert scene.hit_test(visual_path_probe) is path_node

        authored_rectangle_probe = Point(315.0, 155.0)
        visual_rectangle_probe = rectangle_node.transform.transform_point(
            authored_rectangle_probe
        )
        assert scene.hit_test(visual_rectangle_probe) is rectangle_node

        authored_image_probe = Point(495.0, 160.0)
        visual_image_probe = image_node.transform.transform_point(authored_image_probe)
        assert scene.hit_test(visual_image_probe) is image_node

        authored_text_probe = Point(310.0, 310.0)
        visual_text_probe = text_node.transform.transform_point(authored_text_probe)
        assert scene.hit_test(visual_text_probe) is text_node

        authored_clipped_probe = Point(90.0, 300.0)
        visual_clipped_probe = clip_group.transform.transform_point(authored_clipped_probe)
        assert scene.hit_test(visual_clipped_probe) is clipped_path

        path_node.transform = Affine2D.rotation(
            math.radians(-17.0),
            origin=Point(140.0, 160.0),
        )
        rectangle_node.transform = Affine2D.rotation(
            math.radians(14.0),
            origin=Point(320.0, 158.0),
        )
        image_node.transform = Affine2D.rotation(
            math.radians(-23.0),
            origin=Point(495.0, 160.0),
        )
        text_node.transform = Affine2D.uniform_scale(
            0.92,
            origin=Point(310.0, 310.0),
        ).then(Affine2D.translation(-10.0, 7.0))
        clip_group.transform = Affine2D.rotation(
            math.radians(-9.0),
            origin=Point(87.5, 302.5),
        )
        scene.touch()
        renderer.render(window, None)

        assert renderer.frames_rendered == 2
        assert renderer.last_path_count > 4
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 1
        assert renderer.persistent_context_count == 1
        visual_path_probe = path_node.transform.transform_point(authored_path_probe)
        assert scene.hit_test(visual_path_probe) is path_node
        visual_rectangle_probe = rectangle_node.transform.transform_point(
            authored_rectangle_probe
        )
        assert scene.hit_test(visual_rectangle_probe) is rectangle_node
        visual_image_probe = image_node.transform.transform_point(authored_image_probe)
        assert scene.hit_test(visual_image_probe) is image_node
        visual_text_probe = text_node.transform.transform_point(authored_text_probe)
        assert scene.hit_test(visual_text_probe) is text_node
        visual_clipped_probe = clip_group.transform.transform_point(authored_clipped_probe)
        assert scene.hit_test(visual_clipped_probe) is clipped_path
    finally:
        app.stop()
