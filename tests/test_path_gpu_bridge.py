import pytest

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import (
    Color,
    PathGeometry,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


class PathAwareContext:
    adapter_name = "Path Fake GPU"
    graphics_backend = "path-test"

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
        return (len(rectangles), len(texts), len(images), len(paths))

    def clear(self, *background: object) -> None:
        self.clear_calls.append(background)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class PathAwareNative:
    def __init__(self) -> None:
        self.contexts: list[PathAwareContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> PathAwareContext:
        context = PathAwareContext(hwnd, width, height)
        self.contexts.append(context)
        return context


class LegacyContext:
    adapter_name = "Legacy Fake GPU"
    graphics_backend = "legacy-test"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height

    def draw_scene(
        self,
        rectangles: object,
        texts: object,
        images: object,
        *background: object,
    ) -> tuple[int, int, int]:
        assert isinstance(rectangles, list)
        assert isinstance(texts, list)
        assert isinstance(images, list)
        return (len(rectangles), len(texts), len(images))

    def clear(self, *background: object) -> None:
        del background

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class LegacyNative:
    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> LegacyContext:
        return LegacyContext(hwnd, width, height)


def _concave_path() -> PathGeometry:
    return PathGeometry.polygon(
        Point(20, 20),
        Point(180, 20),
        Point(180, 80),
        Point(100, 55),
        Point(20, 80),
    )


def test_wgpu_renderer_submits_tessellated_path_with_opacity_and_clip() -> None:
    native = PathAwareNative()
    renderer = WgpuRenderer(native_module=native)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 320, 220),
        opacity=0.5,
    )
    clipped = SceneNode(
        key="clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(30, 25, 130, 100),
        clip_to_bounds=True,
        opacity=0.8,
    )
    clipped.add(
        SceneNode(
            key="concave",
            kind=SceneNodeKind.PATH,
            bounds=_concave_path().bounds,
            path=_concave_path(),
            fill=Color(0.1, 0.6, 1.0, 0.75),
            opacity=0.5,
        )
    )
    root.add(clipped)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=320, height=220)
    window.set_scene(Scene(320, 220, root))
    app.add_window(window)

    app.start()
    try:
        assert renderer.last_path_count == 3
        assert renderer.last_rectangle_count == 0
        assert renderer.last_text_count == 0
        assert renderer.last_image_count == 0
        context = native.contexts[0]
        assert len(context.path_calls) == 1
        paths = context.path_calls[0][3]
        assert isinstance(paths, list)
        assert len(paths) == 3
        assert all(len(instance) == 14 for instance in paths)
        assert all(instance[6:9] == (0.1, 0.6, 1.0) for instance in paths)
        assert all(instance[9] == pytest.approx(0.15) for instance in paths)
        assert all(instance[10:] == (30.0, 25.0, 160.0, 125.0) for instance in paths)
    finally:
        app.stop()


def test_wgpu_renderer_scales_path_geometry_and_clip_to_physical_pixels() -> None:
    native = PathAwareNative()
    renderer = WgpuRenderer(native_module=native)
    polygon = PathGeometry.polygon(Point(10, 20), Point(90, 20), Point(50, 70))
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 200, 120),
        clip_to_bounds=True,
    )
    root.add(
        SceneNode(
            key="triangle",
            kind=SceneNodeKind.PATH,
            bounds=polygon.bounds,
            path=polygon,
            fill=Color.from_hex("#00A8FF"),
        )
    )

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=200, height=120)
    window.set_scene(Scene(200, 120, root))
    app.add_window(window)

    app.start()
    try:
        window.scale = 1.5
        renderer.render(window, None)
        paths = native.contexts[0].path_calls[-1][3]
        assert isinstance(paths, list)
        assert len(paths) == 1
        assert paths[0][:6] == (15.0, 30.0, 135.0, 30.0, 75.0, 105.0)
        assert paths[0][10:] == (0.0, 0.0, 300.0, 180.0)
    finally:
        app.stop()


def test_wgpu_renderer_fails_explicitly_when_native_core_lacks_path_support() -> None:
    renderer = WgpuRenderer(native_module=LegacyNative())
    polygon = PathGeometry.polygon(Point(10, 10), Point(80, 10), Point(40, 70))
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 120, 90),
    )
    root.add(
        SceneNode(
            key="path",
            kind=SceneNodeKind.PATH,
            bounds=polygon.bounds,
            path=polygon,
            fill=Color.from_hex("#FFFFFF"),
        )
    )

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=120, height=90)
    window.set_scene(Scene(120, 90, root))
    app.add_window(window)

    with pytest.raises(RuntimeError, match="does not support path rendering"):
        app.start()
    app.stop()
