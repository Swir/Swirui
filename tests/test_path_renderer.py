import pytest

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import (
    Color,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


class FakePathContext:
    adapter_name = "Path Fake GPU"
    graphics_backend = "path-test-backend"

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
        shapes: object,
        *background: object,
    ) -> tuple[int, int, int, int]:
        self.path_calls.append((rectangles, texts, images, shapes, *background))
        assert isinstance(rectangles, list)
        assert isinstance(texts, list)
        assert isinstance(images, list)
        assert isinstance(shapes, list)
        return (len(rectangles), len(texts), len(images), len(shapes) // 3)

    def clear(self, *background: object) -> None:
        self.clear_calls.append(background)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class FakePathNative:
    def __init__(self) -> None:
        self.contexts: list[FakePathContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakePathContext:
        context = FakePathContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def test_wgpu_renderer_tessellates_clipped_concave_path_for_native_gpu() -> None:
    native = FakePathNative()
    renderer = WgpuRenderer(native_module=native)

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
    )
    clipped = SceneNode(
        key="clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(80, 60, 260, 220),
        clip_to_bounds=True,
        opacity=0.5,
    )
    path = Path2D.polygon(
        Point(0, 0),
        Point(180, 0),
        Point(180, 60),
        Point(75, 60),
        Point(75, 180),
        Point(0, 180),
    )
    clipped.add(
        SceneNode(
            key="concave",
            kind=SceneNodeKind.PATH,
            bounds=Rect(50, 40, 180, 180),
            fill=Color(0.0, 0.55, 1.0, 0.8),
            opacity=0.75,
            path=path,
        )
    )
    root.add(clipped)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(Scene(640, 360, root))
    app.add_window(window)
    app.start()

    context = native.contexts[0]
    assert len(context.path_calls) == 1
    rectangles, texts, images, shapes = context.path_calls[0][:4]
    assert rectangles == []
    assert texts == []
    assert images == []
    assert isinstance(shapes, list)
    assert len(shapes) == 12
    assert renderer.last_path_count == 4
    assert renderer.last_rectangle_count == 0
    assert renderer.last_text_count == 0
    assert renderer.last_image_count == 0

    first = shapes[0]
    assert first[2:5] == (0.0, 0.55, 1.0)
    assert first[5] == pytest.approx(0.3)
    assert first[6:] == (80.0, 60.0, 340.0, 280.0)
    assert all(vertex[6:] == first[6:] for vertex in shapes)
    assert min(vertex[0] for vertex in shapes) == 50.0
    assert min(vertex[1] for vertex in shapes) == 40.0

    app.stop()
