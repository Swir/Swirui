from __future__ import annotations

from swirui import App, Window
from swirui.platforms import (
    DisplayInfo,
    NativeWindowHandle,
    NativeWindowSpec,
    NullPlatformBackend,
    PlatformEvent,
    PlatformEventKind,
)
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


class ScaledNullBackend(NullPlatformBackend):
    name = "scaled-headless"

    def __init__(self, scale: float = 1.5) -> None:
        super().__init__()
        self.scale = scale
        self.created_specs: list[NativeWindowSpec] = []
        self.resize_calls: list[tuple[int, int]] = []

    def displays(self) -> tuple[DisplayInfo, ...]:
        return (
            DisplayInfo(
                "Scaled display",
                2560,
                1440,
                scale=self.scale,
                primary=True,
                refresh_rate_hz=144.0,
            ),
        )

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle:
        self.created_specs.append(spec)
        return super().create_window(spec)

    def window_scale(self, handle: NativeWindowHandle) -> float:
        self._require_window(handle)
        return self.scale

    def window_display(self, handle: NativeWindowHandle) -> DisplayInfo | None:
        self._require_window(handle)
        return self.displays()[0]

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None:
        self.resize_calls.append((width, height))
        super().resize_window(handle, width, height)


class FakeGpuContext:
    adapter_name = "HiDPI Fake GPU"
    graphics_backend = "hidpi-test"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.scene_calls: list[tuple[object, object, object]] = []
        self.resize_calls: list[tuple[int, int]] = []
        self.images: dict[str, tuple[int, int, bytes]] = {}

    def register_image_rgba(
        self, resource_id: str, width: int, height: int, rgba: bytes
    ) -> None:
        self.images[resource_id] = (width, height, bytes(rgba))

    def unregister_image(self, resource_id: str) -> bool:
        return self.images.pop(resource_id, None) is not None

    def draw_scene(
        self,
        rectangles: object,
        texts: object,
        images: object,
        *_background: object,
    ) -> tuple[int, int, int]:
        self.scene_calls.append((rectangles, texts, images))
        assert isinstance(rectangles, list)
        assert isinstance(texts, list)
        assert isinstance(images, list)
        return (len(rectangles), len(texts), len(images))

    def clear(self, *_background: object) -> None:
        return None

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.resize_calls.append((width, height))


class FakeGpuNative:
    def __init__(self) -> None:
        self.contexts: list[FakeGpuContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakeGpuContext:
        context = FakeGpuContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def _scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 960, 640),
    )
    root.add(
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(80, 40, 200, 100),
            fill=Color.from_hex("#008CFF"),
            corner_radius=CornerRadius.uniform(12),
        ),
        SceneNode(
            key="label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(100, 170, 320, 48),
            text="DPI aware",
            font_size=24,
        ),
        SceneNode(
            key="image",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(500, 100, 160, 120),
            resource_id="pixel",
        ),
    )
    return Scene(960, 640, root)


def test_hidpi_runtime_keeps_scene_and_input_in_logical_dips() -> None:
    backend = ScaledNullBackend(1.5)
    native = FakeGpuNative()
    renderer = WgpuRenderer(native_module=native)
    renderer.register_image_rgba("pixel", 1, 1, bytes((255, 255, 255, 255)))
    window = Window(width=960, height=640)
    window.set_scene(_scene())
    pointer_events: list[object] = []
    window.on("pointer_move", lambda event: pointer_events.append(event))

    app = App(platform_backend=backend, renderer=renderer)
    app.add_window(window)
    app.start()

    assert backend.created_specs[0].width == 1440
    assert backend.created_specs[0].height == 960
    assert (window.width, window.height) == (960, 640)
    assert window.pixel_size == (1440, 960)
    assert window.logical_to_physical(10.0) == 15.0
    assert window.physical_to_logical(15.0) == 10.0

    context = native.contexts[0]
    assert (context.width, context.height) == (1440, 960)
    rectangles, texts, images = context.scene_calls[0]
    assert isinstance(rectangles, list)
    assert isinstance(texts, list)
    assert isinstance(images, list)
    assert rectangles[0][:4] == (120.0, 60.0, 300.0, 150.0)
    assert rectangles[0][8:12] == (18.0, 18.0, 18.0, 18.0)
    assert rectangles[0][12:] == (0.0, 0.0, 1440.0, 960.0)
    assert texts[0][1:6] == (150.0, 255.0, 480.0, 72.0, 36.0)
    assert texts[0][11] == (0.0, 0.0, 1440.0, 960.0)
    assert images[0][1:5] == (750.0, 150.0, 240.0, 180.0)
    assert images[0][6] == (0.0, 0.0, 1440.0, 960.0)

    assert window.native_handle is not None
    handle = window.native_handle
    backend.post_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=150.0, y=90.0)
    )
    app.process_events()

    assert len(pointer_events) == 1
    routed = pointer_events[0]
    logical_event = routed.data["event"]
    assert logical_event.x == 100.0
    assert logical_event.y == 60.0
    assert routed.data["target"].key == "card"

    backend.post_event(
        PlatformEvent(PlatformEventKind.RESIZE, handle, width=1200, height=900)
    )
    app.process_events()
    assert (window.width, window.height) == (800, 600)
    assert window.pixel_size == (1200, 900)
    assert context.resize_calls[-1] == (1200, 900)

    # Win32 SetWindowPos during WM_DPICHANGED can enqueue WM_SIZE first.
    # The runtime normalizes that adjacent pair so the physical 1600x1200
    # resize is interpreted using the incoming 200% scale, preserving 800x600 DIPs.
    backend.scale = 2.0
    backend.post_event(
        PlatformEvent(PlatformEventKind.RESIZE, handle, width=1600, height=1200)
    )
    backend.post_event(PlatformEvent(PlatformEventKind.DPI_CHANGED, handle, scale=2.0))
    app.process_events()
    assert window.scale == 2.0
    assert (window.width, window.height) == (800, 600)
    assert window.pixel_size == (1600, 1200)
    assert context.resize_calls[-1] == (1600, 1200)

    renderer.render(window, None)
    rectangles, texts, images = context.scene_calls[-1]
    assert isinstance(rectangles, list)
    assert isinstance(texts, list)
    assert isinstance(images, list)
    assert rectangles[0][:4] == (160.0, 80.0, 400.0, 200.0)
    assert texts[0][1:6] == (200.0, 340.0, 640.0, 96.0, 48.0)
    assert images[0][1:5] == (1000.0, 200.0, 320.0, 240.0)

    window.resize(700, 500)
    assert backend.resize_calls[-1] == (1400, 1000)

    app.stop()
