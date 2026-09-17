from __future__ import annotations

from typing import Any

from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import (
    BackdropBlur,
    Color,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


class FakeBackdropContext:
    adapter_name = "Backdrop Fake GPU"
    graphics_backend = "backdrop-test"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.calls: list[tuple[Any, ...]] = []
        self.blur_radius = 0.0

    def set_postprocess_blur_radius(self, radius: float) -> None:
        self.blur_radius = radius

    def draw_scene_with_backdrops(self, *args: Any) -> tuple[int, int, int, int, int]:
        self.calls.append(args)
        rectangles, texts, images, paths, backdrops = args[:5]
        return (
            sum(len(segment) for segment in rectangles),
            sum(len(segment) for segment in texts),
            sum(len(segment) for segment in images),
            sum(len(segment) for segment in paths) // 3,
            len(backdrops),
        )

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class FakeBackdropNative:
    def __init__(self) -> None:
        self.contexts: list[FakeBackdropContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakeBackdropContext:
        context = FakeBackdropContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def _backdrop_scene() -> Scene:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 640, 360))
    background = SceneNode(
        "background",
        SceneNodeKind.RECTANGLE,
        Rect(0, 0, 640, 360),
        fill=Color.from_hex("#061226"),
        z_index=0,
    )
    glass = BackdropBlur(radius=16.0).to_scene_node(
        "glass",
        Rect(80, 60, 320, 180),
        z_index=1,
    )
    glass.add(
        SceneNode(
            "glass-tint",
            SceneNodeKind.RECTANGLE,
            Rect(80, 60, 320, 180),
            fill=Color(0.2, 0.55, 1.0, 0.18),
        ),
        SceneNode(
            "glass-title",
            SceneNodeKind.TEXT,
            Rect(112, 96, 220, 40),
            text="Backdrop blur",
            fill=Color.from_hex("#FFFFFF"),
            font_size=24,
        ),
    )
    foreground = SceneNode(
        "foreground",
        SceneNodeKind.RECTANGLE,
        Rect(440, 100, 120, 80),
        fill=Color.from_hex("#00A7FF"),
        z_index=2,
    )
    root.add(background, glass, foreground)
    return Scene(640, 360, root)


def test_backdrop_payload_splits_painter_order_and_scales_to_physical_pixels() -> None:
    renderer = WgpuRenderer(native_module=FakeBackdropNative())
    window = Window(width=640, height=360)
    window.scale = 2.0
    window.set_scene(_backdrop_scene())

    payload = renderer._backdrop_payload(window)
    assert payload is not None
    rectangles, texts, images, paths, backdrops = payload

    assert len(rectangles) == len(texts) == len(images) == len(paths) == 2
    assert len(rectangles[0]) == 1
    assert len(rectangles[1]) == 2
    assert len(texts[0]) == 0
    assert len(texts[1]) == 1
    assert images == [[], []]
    assert paths == [[], []]
    assert backdrops == [(160.0, 120.0, 640.0, 360.0, 32.0, 32.0, 32.0, 32.0, 32.0)]
    assert rectangles[1][0][12:] == (160.0, 120.0, 800.0, 480.0)
    assert texts[1][0][11] == (160.0, 120.0, 800.0, 480.0)


def test_backdrop_scene_uses_persistent_native_segmented_path() -> None:
    native = FakeBackdropNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    window.set_scene(_backdrop_scene())
    app.add_window(window)

    app.start()

    context = native.contexts[0]
    assert len(context.calls) == 1
    rectangles, texts, images, paths, backdrops = context.calls[0][:5]
    assert [len(segment) for segment in rectangles] == [1, 2]
    assert [len(segment) for segment in texts] == [0, 1]
    assert images == [[], []]
    assert paths == [[], []]
    assert backdrops == [(80.0, 60.0, 320.0, 180.0, 16.0, 16.0, 16.0, 16.0, 16.0)]
    assert renderer.last_rectangle_count == 3
    assert renderer.last_text_count == 1
    assert renderer.last_backdrop_count == 1
    assert renderer.frames_rendered == 1
    assert renderer.adapter_name == "Backdrop Fake GPU"

    app.stop()
