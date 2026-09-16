from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


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


class FakePersistentContext:
    adapter_name = "Persistent Fake GPU"
    graphics_backend = "persistent-test-backend"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.draw_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []
        self.resize_calls: list[tuple[int, int]] = []

    def draw_rectangles(self, rectangles: object, *background: object) -> int:
        self.draw_calls.append((rectangles, *background))
        assert isinstance(rectangles, list)
        return len(rectangles)

    def clear(self, *background: object) -> None:
        self.clear_calls.append(background)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.resize_calls.append((width, height))


class FakePersistentNative(FakeNativeGpu):
    def __init__(self) -> None:
        super().__init__()
        self.contexts: list[FakePersistentContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakePersistentContext:
        context = FakePersistentContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def _rectangle_scene(width: int = 800, height: int = 500) -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, width, height),
    )
    root.add(
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(40, 50, 240, 120),
            fill=Color.from_hex("#008CFF"),
            opacity=0.75,
            corner_radius=CornerRadius(12, 18, 24, 30),
        ),
        SceneNode(
            key="ignored-text",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(50, 70, 160, 30),
            text="SwirUI",
            fill=Color.from_hex("#FFFFFF"),
        ),
    )
    return Scene(width, height, root)


def test_wgpu_renderer_submits_scene_rectangles() -> None:
    native = FakeNativeGpu()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="GPU scene", width=800, height=500)
    window.set_scene(_rectangle_scene())
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
    assert submitted[0][8:] == (12, 18, 24, 30)

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


def test_wgpu_renderer_reuses_persistent_context_and_resizes_it() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="Persistent GPU", width=800, height=500)
    window.set_scene(_rectangle_scene())
    app.add_window(window)

    app.start()

    assert len(native.contexts) == 1
    assert renderer.persistent_context_count == 1
    context = native.contexts[0]
    assert len(context.draw_calls) == 1
    assert renderer.adapter_name == "Persistent Fake GPU"
    assert renderer.graphics_backend == "persistent-test-backend"

    renderer.render(window, None)
    assert len(context.draw_calls) == 2
    assert len(native.contexts) == 1

    renderer.resize_surface(window, 900, 600)
    assert context.resize_calls == [(900, 600)]
    assert (context.width, context.height) == (900, 600)

    app.stop()
    assert renderer.persistent_context_count == 0
