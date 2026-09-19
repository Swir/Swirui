from __future__ import annotations

import math

import pytest

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Color, Point, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer
from swirui.rendering.affine import Affine2D
from swirui.rendering.affine_clipping import (
    point_in_convex_polygon,
    transformed_rect_polygon,
)


class _FakeAffineTextContext:
    adapter_name = "Affine Text Fake GPU"
    graphics_backend = "affine-text-test"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.path_calls: list[tuple[object, ...]] = []
        self.image_uploads: list[tuple[str, int, int, bytes]] = []

    def draw_scene_with_paths(
        self,
        rectangles: object,
        texts: object,
        images: object,
        paths: object,
        *background: object,
    ) -> tuple[int, int, int, int]:
        self.path_calls.append((rectangles, texts, images, paths, *background))
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
        self.image_uploads = [entry for entry in self.image_uploads if entry[0] != resource_id]
        return len(self.image_uploads) != before

    def clear(self, *_background: object) -> None:
        pass

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class _FakeAffineTextNative:
    def __init__(self) -> None:
        self.contexts: list[_FakeAffineTextContext] = []
        self.raster_calls: list[tuple[object, ...]] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> _FakeAffineTextContext:
        context = _FakeAffineTextContext(hwnd, width, height)
        self.contexts.append(context)
        return context

    def rasterize_text_rgba(
        self,
        content: str,
        width: int,
        height: int,
        font_size: float,
        red: float,
        green: float,
        blue: float,
        alpha: float,
        family: str,
    ) -> bytes:
        self.raster_calls.append(
            (content, width, height, font_size, red, green, blue, alpha, family)
        )
        pixel = bytes(
            (
                round(red * 255),
                round(green * 255),
                round(blue * 255),
                round(alpha * 255),
            )
        )
        return pixel * (width * height)


def _text_node(*, transform: Affine2D | None = None) -> SceneNode:
    return SceneNode(
        key="affine-text",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(90.0, 80.0, 180.0, 56.0),
        text="Affine Ω text",
        fill=Color.from_hex("#62E5FF"),
        font_size=24.0,
        transform=transform or Affine2D(),
    )


def _start_scene(scene: Scene, native: _FakeAffineTextNative) -> tuple[App, WgpuRenderer, Window]:
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=int(scene.width), height=int(scene.height))
    window.set_scene(scene)
    app.add_window(window)
    app.start()
    return app, renderer, window


def test_rotated_shaped_text_uses_cached_affine_image_pipeline() -> None:
    native = _FakeAffineTextNative()
    text = _text_node(
        transform=Affine2D.rotation(math.radians(23.0), origin=Point(180.0, 108.0))
    )
    scene = Scene(420.0, 300.0, text)
    app, renderer, _window = _start_scene(scene, native)

    try:
        context = native.contexts[0]
        assert len(native.raster_calls) == 1
        assert len(context.image_uploads) == 1
        rectangles, texts, images, paths = context.path_calls[-1][:4]
        assert rectangles == []
        assert texts == []
        assert paths == []
        assert len(images) == 1
        packed = images[0]
        assert len(packed) == 8
        assert packed[0] == context.image_uploads[0][0]
        assert packed[7] == pytest.approx(
            (
                text.transform.m11,
                text.transform.m12,
                text.transform.m21,
                text.transform.m22,
                text.transform.tx,
                text.transform.ty,
            )
        )
        assert renderer.last_text_count == 0
        assert renderer.last_image_count == 1
        assert renderer.affine_text_cache_size == 1
    finally:
        app.stop()


def test_angle_only_updates_reuse_shaped_text_raster() -> None:
    native = _FakeAffineTextNative()
    text = _text_node(
        transform=Affine2D.rotation(math.radians(12.0), origin=Point(180.0, 108.0))
    )
    scene = Scene(420.0, 300.0, text)
    app, renderer, window = _start_scene(scene, native)

    try:
        assert len(native.raster_calls) == 1
        first_resource = native.contexts[0].image_uploads[0][0]
        text.transform = Affine2D.rotation(
            math.radians(57.0),
            origin=Point(180.0, 108.0),
        )
        scene.touch()
        renderer.render(window, None)
        assert len(native.raster_calls) == 1
        assert len(native.contexts[0].image_uploads) == 1
        assert native.contexts[0].path_calls[-1][2][0][0] == first_resource
    finally:
        app.stop()


def test_rotated_clip_uses_exact_uv_preserving_text_triangles() -> None:
    native = _FakeAffineTextNative()
    parent = SceneNode(
        key="rotated-text-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(75.0, 58.0, 230.0, 155.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(math.radians(17.0), origin=Point(190.0, 135.0)),
    )
    text = _text_node()
    parent.add(text)
    scene = Scene(420.0, 300.0, parent)
    app, renderer, _window = _start_scene(scene, native)

    try:
        _rectangles, texts, images, _paths = native.contexts[0].path_calls[-1][:4]
        assert texts == []
        assert images
        assert renderer.last_image_count == len(images)
        clip_polygon = transformed_rect_polygon(parent.transform, parent.bounds)
        for triangle in images:
            assert len(triangle) == 6
            for vertex in triangle[1:4]:
                assert len(vertex) == 4
                assert point_in_convex_polygon(Point(vertex[0], vertex[1]), clip_polygon)
                assert 0.0 <= vertex[2] <= 1.0
                assert 0.0 <= vertex[3] <= 1.0
    finally:
        app.stop()


def test_non_uniform_scale_oversamples_affine_text_texture() -> None:
    native = _FakeAffineTextNative()
    text = _text_node(transform=Affine2D(m11=2.0, m22=0.5, tx=10.0, ty=5.0))
    scene = Scene(520.0, 320.0, text)
    app, renderer, _window = _start_scene(scene, native)

    try:
        assert len(native.raster_calls) == 1
        call = native.raster_calls[0]
        assert call[1] == 360
        assert call[2] == 112
        assert call[3] == pytest.approx(48.0)
        assert renderer.last_image_count == 1
    finally:
        app.stop()
