from __future__ import annotations

import math

import pytest

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
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
from swirui.rendering.affine_clipping import (
    point_in_convex_polygon,
    transformed_rect_polygon,
)


class _FakeAffineContext:
    adapter_name = "Affine Fake GPU"
    graphics_backend = "affine-test-backend"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.path_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []
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

    def clear(self, *background: object) -> None:
        self.clear_calls.append(background)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class _FakeAffineNative:
    def __init__(self) -> None:
        self.contexts: list[_FakeAffineContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> _FakeAffineContext:
        context = _FakeAffineContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def _triangle() -> Path2D:
    return Path2D.polygon(Point(0.0, 0.0), Point(120.0, 0.0), Point(60.0, 100.0))


def test_affine_path_renderer_packs_composed_world_transform_and_clip() -> None:
    native = _FakeAffineNative()
    renderer = WgpuRenderer(native_module=native)

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 500.0, 360.0),
        hit_testable=False,
    )
    parent = SceneNode(
        key="translated-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(80.0, 60.0, 260.0, 200.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.translation(20.0, 10.0),
    )
    path_node = SceneNode(
        key="rotated-path",
        kind=SceneNodeKind.PATH,
        bounds=Rect(110.0, 90.0, 120.0, 100.0),
        fill=Color.from_hex("#0088FF"),
        path=_triangle(),
        transform=Affine2D.rotation(
            math.radians(25.0),
            origin=Point(170.0, 140.0),
        ),
    )
    parent.add(path_node)
    root.add(parent)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=500, height=360)
    window.set_scene(Scene(500.0, 360.0, root))
    app.add_window(window)

    try:
        app.start()
        context = native.contexts[0]
        assert len(context.path_calls) == 1
        rectangles, texts, images, paths = context.path_calls[0][:4]
        assert rectangles == []
        assert texts == []
        assert images == []
        assert isinstance(paths, list)
        assert len(paths) == 3
        assert renderer.last_path_count == 1

        expected_world = path_node.transform.then(parent.transform)
        expected_transform = (
            expected_world.m11,
            expected_world.m12,
            expected_world.m21,
            expected_world.m22,
            expected_world.tx,
            expected_world.ty,
        )
        for vertex in paths:
            assert len(vertex) == 16
            assert vertex[6:10] == (100.0, 70.0, 360.0, 270.0)
            assert vertex[10:16] == pytest.approx(expected_transform)
    finally:
        app.stop()


def test_affine_path_renderer_clips_geometry_to_rotated_parent_exactly() -> None:
    native = _FakeAffineNative()
    renderer = WgpuRenderer(native_module=native)
    clipped = SceneNode(
        key="rotated-clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(70.0, 60.0, 240.0, 180.0),
        clip_to_bounds=True,
        hit_testable=False,
        transform=Affine2D.rotation(math.radians(18.0), origin=Point(190.0, 150.0)),
    )
    clipped.add(
        SceneNode(
            key="path",
            kind=SceneNodeKind.PATH,
            bounds=Rect(50.0, 45.0, 300.0, 230.0),
            fill=Color.from_hex("#62E5FF"),
            path=Path2D.polygon(
                Point(0.0, 0.0),
                Point(300.0, 35.0),
                Point(260.0, 230.0),
                Point(35.0, 205.0),
            ),
        )
    )
    scene = Scene(420.0, 300.0, clipped)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=420, height=300)
    window.set_scene(scene)
    app.add_window(window)

    try:
        app.start()
        context = native.contexts[0]
        rectangles, texts, images, paths = context.path_calls[0][:4]
        assert rectangles == []
        assert texts == []
        assert images == []
        assert isinstance(paths, list)
        assert paths
        assert len(paths) % 3 == 0

        clip_polygon = transformed_rect_polygon(clipped.transform, clipped.bounds)
        for vertex in paths:
            assert len(vertex) == 16
            assert vertex[6:10] == (0.0, 0.0, 420.0, 300.0)
            assert vertex[10:16] == pytest.approx((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
            assert point_in_convex_polygon(Point(vertex[0], vertex[1]), clip_polygon)
    finally:
        app.stop()


def test_affine_path_renderer_tessellates_rotated_rounded_rectangle() -> None:
    native = _FakeAffineNative()
    renderer = WgpuRenderer(native_module=native)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 360.0, 240.0),
        hit_testable=False,
    )
    rectangle = SceneNode(
        key="rotated-rounded-rectangle",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(80.0, 70.0, 140.0, 80.0),
        fill=Color.from_hex("#0088FF"),
        corner_radius=CornerRadius(24.0, 18.0, 10.0, 4.0),
        transform=Affine2D.rotation(math.radians(12.0), origin=Point(150.0, 110.0)),
    )
    root.add(rectangle)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=360, height=240)
    window.set_scene(Scene(360.0, 240.0, root))
    app.add_window(window)

    try:
        app.start()
        context = native.contexts[0]
        rectangles, texts, images, paths = context.path_calls[0][:4]
        assert rectangles == []
        assert texts == []
        assert images == []
        assert isinstance(paths, list)
        assert len(paths) % 3 == 0
        assert len(paths) // 3 > 2
        assert renderer.last_rectangle_count == 0
        assert renderer.last_path_count == len(paths) // 3

        expected_transform = (
            rectangle.transform.m11,
            rectangle.transform.m12,
            rectangle.transform.m21,
            rectangle.transform.m22,
            rectangle.transform.tx,
            rectangle.transform.ty,
        )
        for vertex in paths:
            assert len(vertex) == 16
            assert vertex[6:10] == (0.0, 0.0, 360.0, 240.0)
            assert vertex[10:16] == pytest.approx(expected_transform)
    finally:
        app.stop()


def test_affine_path_renderer_packs_rotated_image_for_native_gpu_pipeline() -> None:
    native = _FakeAffineNative()
    renderer = WgpuRenderer(native_module=native)
    renderer.register_image_rgba(
        "badge",
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
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 300.0),
        hit_testable=False,
    )
    image = SceneNode(
        key="rotated-image",
        kind=SceneNodeKind.IMAGE,
        bounds=Rect(120.0, 80.0, 150.0, 110.0),
        resource_id="badge",
        opacity=0.75,
        transform=Affine2D.rotation(math.radians(20.0), origin=Point(195.0, 135.0)),
    )
    root.add(image)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=420, height=300)
    window.set_scene(Scene(420.0, 300.0, root))
    app.add_window(window)

    try:
        app.start()
        context = native.contexts[0]
        assert len(context.image_uploads) == 1
        rectangles, texts, images, paths = context.path_calls[0][:4]
        assert rectangles == []
        assert texts == []
        assert paths == []
        assert len(images) == 1
        packed = images[0]
        assert len(packed) == 8
        assert packed[1:6] == pytest.approx((120.0, 80.0, 150.0, 110.0, 0.75))
        assert packed[6] == (0.0, 0.0, 420.0, 300.0)
        assert packed[7] == pytest.approx(
            (
                image.transform.m11,
                image.transform.m12,
                image.transform.m21,
                image.transform.m22,
                image.transform.tx,
                image.transform.ty,
            )
        )
        assert packed[0] == context.image_uploads[0][0]
        assert renderer.last_image_count == 1
    finally:
        app.stop()


def test_affine_path_renderer_packs_uniform_scale_and_translation_for_shaped_text() -> None:
    native = _FakeAffineNative()
    renderer = WgpuRenderer(native_module=native)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 300.0),
        hit_testable=False,
    )
    text = SceneNode(
        key="scaled-text",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(90.0, 90.0, 180.0, 48.0),
        text="Scaled glyphon text",
        fill=Color.from_hex("#EAF7FF"),
        font_size=22.0,
        transform=Affine2D.uniform_scale(
            1.2,
            origin=Point(180.0, 114.0),
        ).then(Affine2D.translation(12.0, -8.0)),
    )
    root.add(text)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=420, height=300)
    window.set_scene(Scene(420.0, 300.0, root))
    app.add_window(window)

    try:
        app.start()
        context = native.contexts[0]
        rectangles, texts, images, paths = context.path_calls[0][:4]
        assert rectangles == []
        assert images == []
        assert paths == []
        assert len(texts) == 1
        packed = texts[0]
        expected_bounds = text.transform.transform_rect_bounds(text.bounds)
        assert packed[0] == "Scaled glyphon text"
        assert packed[1:5] == pytest.approx(
            (
                expected_bounds.x,
                expected_bounds.y,
                expected_bounds.width,
                expected_bounds.height,
            )
        )
        assert packed[5] == pytest.approx(26.4)
        assert packed[6:10] == pytest.approx((234 / 255, 247 / 255, 1.0, 1.0))
        assert packed[11] == (0.0, 0.0, 420.0, 300.0)
        assert renderer.last_text_count == 1
    finally:
        app.stop()


def test_affine_path_renderer_keeps_rotated_text_gated() -> None:
    native = _FakeAffineNative()
    renderer = WgpuRenderer(native_module=native)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 360.0, 240.0),
        hit_testable=False,
    )
    root.add(
        SceneNode(
            key="rotated-text",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(80.0, 70.0, 140.0, 80.0),
            text="Still gated",
            fill=Color.from_hex("#EAF7FF"),
            transform=Affine2D.rotation(math.radians(12.0), origin=Point(150.0, 110.0)),
        )
    )
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=360, height=240)
    window.set_scene(Scene(360.0, 240.0, root))
    app.add_window(window)

    try:
        with pytest.raises(
            RuntimeError,
            match="text nodes currently require positive uniform scale",
        ):
            app.start()
    finally:
        app.stop()
