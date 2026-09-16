from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Color, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer


class FakeNativeGpu:
    def __init__(self) -> None:
        self.rectangle_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []

    def draw_rectangles_win32_surface(self, *args: object) -> tuple[str, str, int]:
        self.rectangle_calls.append(args)
        rectangles = args[3]
        assert isinstance(rectangles, list)
        return ("Fake GPU", "test-backend", len(rectangles))

    def clear_win32_surface(self, *args: object) -> tuple[str, str]:
        self.clear_calls.append(args)
        return ("Fake GPU", "test-backend")


def test_wgpu_renderer_submits_scene_rectangles() -> None:
    native = FakeNativeGpu()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="GPU scene", width=800, height=500)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 800, 500),
    )
    root.add(
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(40, 50, 240, 120),
            fill=Color.from_hex("#008CFF"),
            opacity=0.75,
        ),
        SceneNode(
            key="ignored-text",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(50, 70, 160, 30),
            text="SwirUI",
            fill=Color.from_hex("#FFFFFF"),
        ),
    )
    window.set_scene(Scene(800, 500, root))
    app.add_window(window)

    app.start()

    assert renderer.frames_rendered == 1
    assert renderer.last_rectangle_count == 1
    assert renderer.adapter_name == "Fake GPU"
    assert renderer.graphics_backend == "test-backend"
    assert len(native.rectangle_calls) == 1
    assert native.clear_calls == []

    submitted = native.rectangle_calls[0][3]
    assert isinstance(submitted, list)
    assert submitted[0][:4] == (40, 50, 240, 120)
    assert submitted[0][7] == 0.75

    app.stop()


def test_wgpu_renderer_clears_when_scene_has_no_rectangles() -> None:
    native = FakeNativeGpu()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(
        Scene(
            640,
            360,
            SceneNode(
                key="root",
                kind=SceneNodeKind.GROUP,
                bounds=Rect(0, 0, 640, 360),
            ),
        )
    )
    app.add_window(window)

    app.start()

    assert renderer.frames_rendered == 1
    assert renderer.last_rectangle_count == 0
    assert len(native.clear_calls) == 1
    assert native.rectangle_calls == []

    app.stop()
