from __future__ import annotations

import sys

import pytest

from swirui import App, Window
from swirui.core import Event
from swirui.platforms import DisplayInfo, NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


class ForcedScaleWin32Backend(Win32PlatformBackend):
    """Real HWND backend with deterministic monitor metrics for mixed-DPI CI."""

    def __init__(self, scale: float) -> None:
        super().__init__()
        self.forced_scale = scale
        self._class_name = f"SwirUI.NativeWindow.HiDPI.{id(self):x}"

    def _display(self) -> DisplayInfo:
        return DisplayInfo(
            "CI mixed-DPI display",
            2560,
            1440,
            scale=self.forced_scale,
            primary=True,
            refresh_rate_hz=144.0,
            work_width=2560,
            work_height=1400,
        )

    def displays(self) -> tuple[DisplayInfo, ...]:
        self._require_initialized()
        return (self._display(),)

    def window_scale(self, handle: NativeWindowHandle) -> float:
        self._require_window(handle)
        return self.forced_scale

    def window_display(self, handle: NativeWindowHandle) -> DisplayInfo | None:
        self._require_window(handle)
        return self._display()

    def post_test_event(self, event: PlatformEvent) -> None:
        self._require_window(event.window)
        self._events.append(event)


def _hidpi_scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 680, 440),
    )
    root.add(
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(100, 50, 220, 120),
            fill=Color.from_hex("#008CFF"),
            corner_radius=CornerRadius.uniform(20),
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(120, 200, 400, 60),
            text="SwirUI HiDPI — Zażółć gęślą jaźń",
            fill=Color.from_hex("#F3FAFF"),
            font_size=24,
        ),
        SceneNode(
            key="image",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(430, 60, 120, 100),
            resource_id="pixel",
        ),
    )
    return Scene(680, 440, root)


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 HiDPI GPU smoke requires Windows")
def test_real_wgpu_surface_tracks_logical_scene_across_dpi_scales() -> None:
    backend = ForcedScaleWin32Backend(1.5)
    renderer = WgpuRenderer()
    renderer.register_image_rgba("pixel", 1, 1, bytes((88, 199, 255, 255)))
    app = App("SwirUI HiDPI GPU Smoke", platform_backend=backend, renderer=renderer)
    window = Window(title="SwirUI HiDPI GPU Smoke", width=680, height=440)
    window.set_scene(_hidpi_scene())
    pointer_observations: list[tuple[float | None, float | None, str | None]] = []

    def capture_pointer(event: Event) -> None:
        platform_event = event.data["event"]
        target = event.data["target"]
        pointer_observations.append(
            (
                platform_event.x,
                platform_event.y,
                target.key if target is not None else None,
            )
        )

    window.on("pointer_move", capture_pointer)
    app.add_window(window)

    try:
        app.start()
        assert window.native_handle is not None
        handle = window.native_handle
        assert window.scale == pytest.approx(1.5)
        assert (window.width, window.height) == (680, 440)
        assert window.pixel_size == (1020, 660)
        surface = renderer.surfaces[handle.value]
        assert (surface.width, surface.height) == (1020, 660)
        assert renderer.persistent_context_count == 1
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 1

        backend.post_test_event(
            PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=225.0, y=120.0)
        )
        app.process_events()
        assert any(
            x == pytest.approx(150.0)
            and y == pytest.approx(80.0)
            and target == "card"
            for x, y, target in pointer_observations
        )

        # WM_SIZE reports client pixels, while SetWindowPos consumes an outer-window
        # size. Inject the normalized client-size event directly so this smoke test
        # exercises the runtime DPI ordering/scaling contract without conflating it
        # with non-client frame metrics (covered independently by the Win32 backend).
        backend.forced_scale = 2.0
        backend.post_test_event(
            PlatformEvent(PlatformEventKind.RESIZE, handle, width=1360, height=880)
        )
        backend.post_test_event(
            PlatformEvent(PlatformEventKind.DPI_CHANGED, handle, scale=2.0)
        )
        backend.post_test_event(PlatformEvent(PlatformEventKind.DISPLAY_CHANGED, handle))
        app.process_events()

        assert window.scale == pytest.approx(2.0)
        assert (window.width, window.height) == (680, 440)
        assert window.pixel_size == (1360, 880)
        assert (surface.width, surface.height) == (1360, 880)
        assert renderer.persistent_context_count == 1

        pointer_observations.clear()
        backend.post_test_event(
            PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=300.0, y=160.0)
        )
        app.process_events()
        assert any(
            x == pytest.approx(150.0)
            and y == pytest.approx(80.0)
            and target == "card"
            for x, y, target in pointer_observations
        )

        renderer.render(window, None)
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
