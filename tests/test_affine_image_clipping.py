from __future__ import annotations

import math

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Point, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer
from swirui.rendering.affine import Affine2D
from swirui.rendering.affine_clipping import (
    point_in_convex_polygon,
    transformed_rect_polygon,
)


class _FakeContext:
    adapter_name = "Affine Image Fake GPU"
    graphics_backend = "affine-image-test"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.calls: list[tuple[object, ...]] = []
        self.image_uploads: list[tuple[str, int, int, bytes]] = []

    def draw_scene_with_paths(
        self,
        rectangles: object,
        texts: object,
        images: object,
        paths: object,
        *background: object,
    ) -> tuple[int, int, int, int]:
        self.calls.append((rectangles, texts, images, paths, *background))
        assert isinstance(rectangles, list)
        assert isinstance(texts, list)
        assert isinstance(images, list)
        assert isinstance(paths, list)
        return len(rectangles), len(texts), len(images), len(paths) // 3

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes,
    ) -> None:
        self.image_uploads.append((resource_id, width, height, bytes(rgba)))

    def unregister_image(self, resource_id: str) -> bool:
        before = len(self.image_uploads)
        self.image_uploads = [item for item in self.image_uploads if item[0] != resource_id]
        return len(self.image_uploads) != before

    def clear(self, *background: object) -> None:
        del background

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class _FakeNative:
    def __init__(self) -> None:
        self.contexts: list[_FakeContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> _FakeContext:
        context = _FakeContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def test_image_is_exactly_triangulated_against_rotated_clip_with_uvs_preserved() -> None:
    native = _FakeNative()
    renderer = WgpuRenderer(native_module=native)
    renderer.register_image_rgba(
        "checker",
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

    clip_group = SceneNode(
        key="rotated-image-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(90.0, 65.0, 180.0, 140.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(
            math.radians(23.0),
            origin=Point(180.0, 135.0),
        ),
    )
    image = SceneNode(
        key="oversized-image",
        kind=SceneNodeKind.IMAGE,
        bounds=Rect(55.0, 35.0, 250.0, 210.0),
        resource_id="checker",
        opacity=0.82,
        transform=Affine2D.rotation(
            math.radians(-11.0),
            origin=Point(180.0, 140.0),
        ),
    )
    clip_group.add(image)
    scene = Scene(360.0, 280.0, clip_group)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=360, height=280)
    window.set_scene(scene)
    app.add_window(window)

    try:
        app.start()
        context = native.contexts[0]
        assert len(context.calls) == 1
        rectangles, texts, images, paths = context.calls[0][:4]
        assert rectangles == []
        assert texts == []
        assert paths == []
        assert isinstance(images, list)
        assert images

        clip_polygon = transformed_rect_polygon(clip_group.transform, clip_group.bounds)
        for triangle in images:
            assert isinstance(triangle, tuple)
            assert len(triangle) == 6
            _, first, second, third, opacity, axis_clip = triangle
            assert opacity == 0.82
            assert axis_clip == (0.0, 0.0, 360.0, 280.0)
            for vertex in (first, second, third):
                assert len(vertex) == 4
                x, y, u, v = vertex
                assert point_in_convex_polygon(Point(x, y), clip_polygon)
                assert 0.0 <= u <= 1.0
                assert 0.0 <= v <= 1.0
    finally:
        app.stop()
