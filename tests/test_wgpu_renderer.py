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
        self.image_resources: dict[str, tuple[int, int, bytes]] = {}
        self.draw_calls: list[tuple[object, ...]] = []
        self.clear_calls: list[tuple[object, ...]] = []
        self.resize_calls: list[tuple[int, int]] = []
        self.blur_radius_calls: list[float] = []
        self.postprocess_blur_radius = 0.0

    def set_postprocess_blur_radius(self, radius: float) -> None:
        self.postprocess_blur_radius = radius
        self.blur_radius_calls.append(radius)

    def register_image_rgba(
        self, resource_id: str, width: int, height: int, rgba: bytes
    ) -> None:
        self.image_resources[resource_id] = (width, height, bytes(rgba))

    def unregister_image(self, resource_id: str) -> bool:
        return self.image_resources.pop(resource_id, None) is not None

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
    assert submitted_rectangles[0][8:12] == (12, 18, 24, 30)
    assert submitted_rectangles[0][12:] == (0.0, 0.0, 800, 500)
    assert submitted_texts[0][:6] == ("SwirUI", 50, 70, 160, 36, 24)
    assert submitted_texts[0][9] == 0.8
    assert submitted_texts[0][10] == "Segoe UI"
    assert submitted_texts[0][11] == (0.0, 0.0, 800, 500)

    app.stop()


def test_wgpu_renderer_inherits_group_opacity_across_mixed_primitives() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    renderer.register_image_rgba("pixel", 1, 1, bytes((255, 255, 255, 255)))

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
        opacity=0.5,
    )
    layer = SceneNode(
        key="layer",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
        opacity=0.5,
    )
    layer.add(
        SceneNode(
            key="rect",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(20, 30, 120, 60),
            fill=Color(0.2, 0.4, 0.8, 0.5),
            opacity=0.8,
        ),
        SceneNode(
            key="text",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(30, 110, 220, 40),
            text="Inherited alpha",
            fill=Color(1.0, 1.0, 1.0, 1.0),
            opacity=0.6,
        ),
        SceneNode(
            key="image",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(280, 40, 100, 100),
            resource_id="pixel",
            opacity=0.4,
        ),
    )
    root.add(layer)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(Scene(640, 360, root))
    app.add_window(window)
    app.start()

    context = native.contexts[0]
    rectangles, texts, images = context.scene_calls[0][:3]
    assert isinstance(rectangles, list)
    assert isinstance(texts, list)
    assert isinstance(images, list)
    assert rectangles[0][7] == 0.1
    assert texts[0][9] == 0.15
    assert images[0][5] == 0.1
    assert rectangles[0][12:] == (0.0, 0.0, 640, 360)
    assert texts[0][11] == (0.0, 0.0, 640, 360)
    assert images[0][6] == (0.0, 0.0, 640, 360)

    app.stop()


def test_wgpu_renderer_submits_nested_clip_for_all_primitive_kinds() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    renderer.register_image_rgba("pixel", 1, 1, bytes((255, 255, 255, 255)))

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
    )
    clipped = SceneNode(
        key="clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(100, 80, 220, 160),
        clip_to_bounds=True,
    )
    clipped.add(
        SceneNode(
            key="rect",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(50, 50, 360, 240),
            fill=Color.from_hex("#008CFF"),
        ),
        SceneNode(
            key="text",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(70, 100, 360, 80),
            text="Clipped GPU text",
        ),
        SceneNode(
            key="image",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(240, 40, 180, 240),
            resource_id="pixel",
        ),
    )
    root.add(clipped)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(Scene(640, 360, root))
    app.add_window(window)
    app.start()

    rectangles, texts, images = native.contexts[0].scene_calls[0][:3]
    assert isinstance(rectangles, list)
    assert isinstance(texts, list)
    assert isinstance(images, list)
    expected_clip = (100, 80, 320, 240)
    assert rectangles[0][12:] == expected_clip
    assert texts[0][11] == expected_clip
    assert images[0][6] == expected_clip

    app.stop()


def test_wgpu_renderer_skips_fully_transparent_subtree_before_resource_lookup() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
        opacity=0.0,
    )
    root.add(
        SceneNode(
            key="hidden-image",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(20, 20, 100, 100),
            resource_id="not-registered",
        )
    )

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(Scene(640, 360, root))
    app.add_window(window)
    app.start()

    context = native.contexts[0]
    assert context.scene_calls == []
    assert len(context.clear_calls) == 1
    assert renderer.last_rectangle_count == 0
    assert renderer.last_text_count == 0
    assert renderer.last_image_count == 0

    app.stop()


def test_wgpu_renderer_uploads_and_submits_registered_image() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native)
    pixels = bytes(
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
    )
    renderer.register_image_rgba("checker", 2, 2, pixels)
    assert renderer.image_resource_count == 1

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 640, 360),
    )
    root.add(
        SceneNode(
            key="image",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(40, 50, 240, 160),
            resource_id="checker",
            opacity=0.65,
        )
    )
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(Scene(640, 360, root))
    app.add_window(window)

    app.start()

    context = native.contexts[0]
    assert context.image_resources["checker"] == (2, 2, pixels)
    assert renderer.last_rectangle_count == 0
    assert renderer.last_text_count == 0
    assert renderer.last_image_count == 1
    submitted_images = context.scene_calls[0][2]
    assert isinstance(submitted_images, list)
    assert submitted_images == [
        ("checker", 40, 50, 240, 160, 0.65, (0.0, 0.0, 640, 360))
    ]

    assert renderer.unregister_image("checker") is True
    assert renderer.image_resource_count == 0
    assert context.image_resources == {}
    app.stop()


def test_wgpu_renderer_rejects_invalid_rgba_resource() -> None:
    renderer = WgpuRenderer(native_module=FakePersistentNative())
    try:
        renderer.register_image_rgba("bad", 2, 2, bytes(15))
    except ValueError as exc:
        assert "exactly 16 bytes" in str(exc)
    else:
        raise AssertionError("Invalid RGBA resource should fail validation")


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
    assert submitted_texts[0][11] == (0.0, 0.0, 640, 360)
    assert renderer.last_rectangle_count == 0
    assert renderer.last_text_count == 1

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


def test_wgpu_renderer_validates_scene_blur_radius() -> None:
    for invalid in (-0.01, 64.01, float("nan"), float("inf")):
        try:
            WgpuRenderer(native_module=FakePersistentNative(), scene_blur_radius=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid scene blur radius should fail: {invalid!r}")


def test_wgpu_renderer_configures_and_updates_persistent_scene_blur() -> None:
    native = FakePersistentNative()
    renderer = WgpuRenderer(native_module=native, scene_blur_radius=12.0)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(title="Blurred GPU", width=800, height=500)
    window.set_scene(_mixed_scene())
    app.add_window(window)

    app.start()

    context = native.contexts[0]
    assert context.postprocess_blur_radius == 12.0
    assert context.blur_radius_calls[0] == 12.0

    renderer.set_scene_blur_radius(20.0)
    assert renderer.scene_blur_radius == 20.0
    assert context.postprocess_blur_radius == 20.0
    assert context.blur_radius_calls[-1] == 20.0

    renderer.set_scene_blur_radius(0.0)
    assert context.postprocess_blur_radius == 0.0
    assert context.blur_radius_calls[-1] == 0.0

    app.stop()
