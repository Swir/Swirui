import pytest

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
        self.scene_calls: list[tuple[object, ...]] = []
        self.rectangle_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []

    def draw_scene_win32_surface(self, *args: object) -> tuple[str, str, int, int]:
        self.scene_calls.append(args)
        rectangles = args[3]
        texts = args[4]
        assert isinstance(rectangles, list)
        assert isinstance(texts, list)
        return ("Fake GPU", "test-backend", len(rectangles), len(texts))

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
        self.scene_calls: list[tuple[object, ...]] = []
        self.draw_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []
        self.resize_calls: list[tuple[int, int]] = []
        self.upload_calls: list[tuple[str, int, int, list[int]]] = []
        self.remove_calls: list[str] = []

    def draw_scene(
        self,
        rectangles: object,
        texts: object,
        images: object,
        *background: object,
    ) -> tuple[int, int, int]:
        self.scene_calls.append((rectangles, texts, images, *background))
        assert isinstance(rectangles, list)
        assert isinstance(texts, list)
        assert isinstance(images, list)
        return (len(rectangles), len(texts), len(images))

    def draw_rectangles(self, rectangles: object, *background: object) -> int:
        self.draw_calls.append((rectangles, *background))
        assert isinstance(rectangles, list)
        return len(rectangles)

    def upload_image(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: list[int],
    ) -> None:
        self.upload_calls.append((resource_id, width, height, rgba))

    def remove_image(self, resource_id: str) -> bool:
        self.remove_calls.append(resource_id)
        return True

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


def _mixed_scene(width: int = 800, height: int = 500) -> Scene:
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
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(50, 70, 160, 36),
            text="SwirUI",
            fill=Color.from_hex("#EAF7FF"),
            opacity=0.8,
            font_size=24,
            font_family="Segoe UI",
        ),
    )
    return Scene(width, height, root)


def _image_scene(width: int = 800, height: int = 500) -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, width, height),
    )
    root.add(
        SceneNode(
            key="logo",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(120, 90, 96, 96),
            opacity=0.85,
            resource_id="logo-rgba",
        )
    )
    scene = Scene(width, height, root)
    scene.register_image_rgba8(
        "logo-rgba",
        2,
        2,
        bytes(
            [
                255,
                0,
                0,
                255,
                0,
                255,
                0,
                255,
                0,
                0,
                255,
                255,
                255,
                255,
                255,
                255,
            ]
        ),
    )
    return scene


def test_wgpu_renderer_submits_scene_rectangles_and_text() -> None:
    native = FakeNativeGpu()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="GPU scene", width=800, height=500)
    window.set_scene(_mixed_scene())
    app.add_window(window)

    app.start()

    assert renderer.frames_rendered == 1
    assert renderer.last_rectangle_count == 1
    assert renderer.last_text_count == 1
    assert renderer.last_image_count == 0
    assert renderer.adapter_name == "Fake GPU"
    assert renderer.graphics_backend == "test-backend"
    assert len(native.scene_calls) == 1
    assert native.rectangle_calls == []
    assert native.clear_calls == []

    submitted_rectangles = native.scene_calls[0][3]
    submitted_texts = native.scene_calls[0][4]
    assert isinstance(submitted_rectangles, list)
    assert isinstance(submitted_texts, list)
    assert submitted_rectangles[0][:4] == (40, 50, 240, 120)
    assert submitted_rectangles[0][7] == 0.75
    assert submitted_rectangles[0][8:] == (12, 18, 24, 30)
    assert submitted_texts[0][:6] == ("SwirUI", 50, 70, 160, 36, 24)
    assert submitted_texts[0][9] == 0.8
    assert submitted_texts[0][10] == "Segoe UI"

    app.stop()


def test_wgpu_renderer_uses_white_for_unfilled_text() -> None:
    native = FakeNativeGpu()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
    )
    root.add(
        SceneNode(
            key="text",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(20, 30, 260, 52),
            text="GPU shaped text",
            opacity=0.5,
            font_size=28,
        )
    )
    window.set_scene(Scene(640, 360, root))
    app.add_window(window)

    app.start()

    submitted_texts = native.scene_calls[0][4]
    assert isinstance(submitted_texts, list)
    assert submitted_texts[0][6:10] == (1.0, 1.0, 1.0, 0.5)
    assert renderer.last_rectangle_count == 0
    assert renderer.last_text_count == 1
    assert renderer.last_image_count == 0

    app.stop()


def test_wgpu_renderer_clears_when_scene_has_no_drawables() -> None:
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
    assert renderer.last_text_count == 0
    assert renderer.last_image_count == 0
    assert len(native.clear_calls) == 1
    assert native.scene_calls == []
    assert native.rectangle_calls == []

    app.stop()


def test_wgpu_renderer_reuses_persistent_context_and_resizes_it() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="Persistent GPU", width=800, height=500)
    window.set_scene(_mixed_scene())
    app.add_window(window)

    app.start()

    assert len(native.contexts) == 1
    assert renderer.persistent_context_count == 1
    context = native.contexts[0]
    assert len(context.scene_calls) == 1
    assert renderer.last_rectangle_count == 1
    assert renderer.last_text_count == 1
    assert renderer.last_image_count == 0
    assert renderer.adapter_name == "Persistent Fake GPU"
    assert renderer.graphics_backend == "persistent-test-backend"

    renderer.render(window, None)
    assert len(context.scene_calls) == 2
    assert len(native.contexts) == 1

    renderer.resize_surface(window, 900, 600)
    assert context.resize_calls == [(900, 600)]
    assert (context.width, context.height) == (900, 600)

    app.stop()
    assert renderer.persistent_context_count == 0


def test_wgpu_renderer_uploads_image_only_when_revision_changes() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="GPU image cache", width=800, height=500)
    scene = _image_scene()
    window.set_scene(scene)
    app.add_window(window)

    app.start()

    context = native.contexts[0]
    assert len(context.upload_calls) == 1
    assert context.upload_calls[0][:3] == ("logo-rgba", 2, 2)
    assert len(context.upload_calls[0][3]) == 16
    assert renderer.last_image_count == 1
    submitted_images = context.scene_calls[0][2]
    assert isinstance(submitted_images, list)
    assert submitted_images[0] == ("logo-rgba", 120, 90, 96, 96, 0.85)

    renderer.render(window, None)
    assert len(context.upload_calls) == 1

    scene.register_image_rgba8("logo-rgba", 2, 2, bytes([20, 40, 60, 255] * 4))
    renderer.render(window, None)
    assert len(context.upload_calls) == 2

    window.set_scene(
        Scene(
            800,
            500,
            SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 800, 500)),
        )
    )
    renderer.render(window, None)
    assert context.remove_calls == ["logo-rgba"]
    assert renderer.last_image_count == 0

    app.stop()


def test_wgpu_renderer_rejects_missing_image_resource() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=320, height=240)
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 320, 240))
    root.add(
        SceneNode(
            "missing",
            SceneNodeKind.IMAGE,
            Rect(10, 10, 32, 32),
            resource_id="not-registered",
        )
    )
    window.set_scene(Scene(320, 240, root))
    app.add_window(window)

    with pytest.raises(RuntimeError, match="missing resource"):
        app.start()

    app.stop()
