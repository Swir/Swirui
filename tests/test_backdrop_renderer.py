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


class FakeCachedBackdropContext(FakeBackdropContext):
    def __init__(self, hwnd: int, width: int, height: int) -> None:
        super().__init__(hwnd, width, height)
        self.cached_tokens: list[int] = []
        self.effect_cache_hits = 0
        self.effect_cache_misses = 0
        self._cached_token: int | None = None
        self._cached_counts: tuple[int, int, int, int, int] | None = None

    def draw_scene_with_backdrops_cached(
        self, *args: Any
    ) -> tuple[int, int, int, int, int]:
        token = int(args[5])
        self.calls.append(args)
        self.cached_tokens.append(token)
        if token == self._cached_token and self._cached_counts is not None:
            self.effect_cache_hits += 1
            return self._cached_counts

        rectangles, texts, images, paths, backdrops = args[:5]
        counts = (
            sum(len(segment) for segment in rectangles),
            sum(len(segment) for segment in texts),
            sum(len(segment) for segment in images),
            sum(len(segment) for segment in paths) // 3,
            len(backdrops),
        )
        self.effect_cache_misses += 1
        self._cached_token = token
        self._cached_counts = counts
        return counts

    def clear_effect_cache(self) -> None:
        self._cached_token = None
        self._cached_counts = None

    def reset_effect_cache_stats(self) -> None:
        self.effect_cache_hits = 0
        self.effect_cache_misses = 0


class FakeBackdropNative:
    def __init__(self) -> None:
        self.contexts: list[FakeBackdropContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakeBackdropContext:
        context = FakeBackdropContext(hwnd, width, height)
        self.contexts.append(context)
        return context


class FakeCachedBackdropNative:
    def __init__(self) -> None:
        self.contexts: list[FakeCachedBackdropContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakeCachedBackdropContext:
        context = FakeCachedBackdropContext(hwnd, width, height)
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


def test_backdrop_payload_cache_reuses_unchanged_scene_and_tracks_stats() -> None:
    renderer = WgpuRenderer(native_module=FakeBackdropNative())
    window = Window(width=640, height=360)
    window.set_scene(_backdrop_scene())

    first = renderer._backdrop_payload(window)
    second = renderer._backdrop_payload(window)

    assert first is not None
    assert second is first
    assert renderer.backdrop_payload_cache_hits == 1
    assert renderer.backdrop_payload_cache_misses == 1
    assert renderer.backdrop_payload_cache_entries == 1

    renderer.reset_backdrop_payload_cache_stats()
    assert renderer.backdrop_payload_cache_hits == 0
    assert renderer.backdrop_payload_cache_misses == 0
    assert renderer.backdrop_payload_cache_entries == 1


def test_backdrop_payload_cache_invalidates_on_scene_touch_and_dpi_change() -> None:
    renderer = WgpuRenderer(native_module=FakeBackdropNative())
    window = Window(width=640, height=360)
    scene = _backdrop_scene()
    window.set_scene(scene)

    first = renderer._backdrop_payload(window)
    assert first is not None

    background = scene.root.children[0]
    new_fill = Color.from_hex("#112233")
    background.fill = new_fill
    scene.touch()
    touched = renderer._backdrop_payload(window)
    assert touched is not None
    assert touched is not first
    assert touched[0][0][0][4:8] == (
        new_fill.r,
        new_fill.g,
        new_fill.b,
        new_fill.a,
    )

    window.scale = 1.5
    scaled = renderer._backdrop_payload(window)
    assert scaled is not None
    assert scaled is not touched
    assert scaled[4][0][:5] == (120.0, 90.0, 480.0, 270.0, 24.0)
    assert renderer.backdrop_payload_cache_hits == 0
    assert renderer.backdrop_payload_cache_misses == 3


def test_backdrop_payload_cache_invalidates_on_scene_replacement_and_image_rebind() -> None:
    renderer = WgpuRenderer(native_module=FakeBackdropNative())
    renderer.register_image_rgba("logo", 1, 1, bytes((0, 64, 255, 255)))
    window = Window(width=640, height=360)

    first_scene = _backdrop_scene()
    first_scene.root.add(
        SceneNode(
            "logo",
            SceneNodeKind.IMAGE,
            Rect(460, 220, 64, 64),
            resource_id="logo",
            z_index=3,
        )
    )
    window.set_scene(first_scene)
    first = renderer._backdrop_payload(window)
    assert first is not None
    assert first[2][1][0][0] == "logo"

    replacement = _backdrop_scene()
    replacement.root.add(
        SceneNode(
            "logo",
            SceneNodeKind.IMAGE,
            Rect(460, 220, 64, 64),
            resource_id="logo",
            z_index=3,
        )
    )
    window.set_scene(replacement)
    replaced = renderer._backdrop_payload(window)
    assert replaced is not None
    assert replaced is not first

    assert renderer._backdrop_payload(window) is replaced
    renderer.register_image_rgba("logo", 1, 1, bytes((255, 32, 0, 255)))
    rebound = renderer._backdrop_payload(window)
    assert rebound is not None
    assert rebound is not replaced
    assert rebound[2][1][0][0] == "logo#1"
    assert renderer.backdrop_payload_cache_hits == 1
    assert renderer.backdrop_payload_cache_misses == 3


def test_backdrop_payload_cache_remembers_scene_without_backdrop() -> None:
    renderer = WgpuRenderer(native_module=FakeBackdropNative())
    window = Window(width=320, height=180)
    window.set_scene(
        Scene(
            320,
            180,
            SceneNode(
                "root",
                SceneNodeKind.RECTANGLE,
                Rect(0, 0, 320, 180),
                fill=Color.from_hex("#101820"),
            ),
        )
    )

    assert renderer._backdrop_payload(window) is None
    assert renderer._backdrop_payload(window) is None
    assert renderer.backdrop_payload_cache_hits == 1
    assert renderer.backdrop_payload_cache_misses == 1

    renderer.clear_backdrop_payload_cache(window)
    assert renderer.backdrop_payload_cache_entries == 0


def test_backdrop_scene_uses_persistent_native_segmented_path() -> None:
    native = FakeBackdropNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    scene = _backdrop_scene()
    window.set_scene(scene)
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
    assert renderer.backdrop_payload_cache_misses == 1

    renderer.render(window, window.root)
    assert len(context.calls) == 2
    assert renderer.backdrop_payload_cache_hits == 1

    scene.touch()
    renderer.render(window, window.root)
    assert len(context.calls) == 3
    assert renderer.backdrop_payload_cache_misses == 2

    app.stop()
    assert renderer.backdrop_payload_cache_entries == 0


def test_backdrop_scene_reuses_native_effect_token_until_retained_scene_changes() -> None:
    native = FakeCachedBackdropNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=640, height=360)
    scene = _backdrop_scene()
    window.set_scene(scene)
    app.add_window(window)

    app.start()
    context = native.contexts[0]
    assert context.effect_cache_misses == 1
    assert context.effect_cache_hits == 0
    assert len(context.cached_tokens) == 1
    first_token = context.cached_tokens[0]

    renderer.render(window, window.root)
    assert context.cached_tokens == [first_token, first_token]
    assert context.effect_cache_hits == 1
    assert context.effect_cache_misses == 1
    assert renderer.native_effect_cache_hits == 1
    assert renderer.native_effect_cache_misses == 1

    scene.touch()
    renderer.render(window, window.root)
    assert context.cached_tokens[-1] != first_token
    assert context.effect_cache_hits == 1
    assert context.effect_cache_misses == 2

    renderer.reset_native_effect_cache_stats()
    assert renderer.native_effect_cache_hits == 0
    assert renderer.native_effect_cache_misses == 0

    renderer.clear_backdrop_payload_cache(window)
    renderer.render(window, window.root)
    assert context.effect_cache_hits == 0
    assert context.effect_cache_misses == 1
    assert context.cached_tokens[-1] != context.cached_tokens[-2]

    app.stop()
