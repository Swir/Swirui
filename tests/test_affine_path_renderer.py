from __future__ import annotations

import math

import pytest

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Color, Path2D, Point, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer
from swirui.rendering.affine import Affine2D


class _FakeAffineContext:
    adapter_name = "Affine Fake GPU"
    graphics_backend = "affine-test-backend"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.path_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []

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


def test_affine_path_renderer_rejects_rotated_clip_instead_of_approximating_it() -> None:
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
            bounds=Rect(100.0, 90.0, 120.0, 100.0),
            fill=Color.from_hex("#62E5FF"),
            path=_triangle(),
        )
    )
    scene = Scene(420.0, 300.0, clipped)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=420, height=300)
    window.set_scene(scene)
    app.add_window(window)

    try:
        with pytest.raises(RuntimeError, match="Rotated or sheared SceneNode clipping"):
            app.start()
    finally:
        app.stop()


def test_affine_path_renderer_keeps_non_path_raster_transforms_gated() -> None:
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
            key="rotated-rectangle",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(80.0, 70.0, 140.0, 80.0),
            fill=Color.from_hex("#0088FF"),
            transform=Affine2D.rotation(math.radians(12.0), origin=Point(150.0, 110.0)),
        )
    )
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=360, height=240)
    window.set_scene(Scene(360.0, 240.0, root))
    app.add_window(window)

    try:
        with pytest.raises(RuntimeError, match="rectangle nodes require"):
            app.start()
    finally:
        app.stop()
