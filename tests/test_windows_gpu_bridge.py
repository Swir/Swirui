import importlib
import sys

import pytest

from swirui import App, Window
from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, CornerRadius, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU bridge test requires Windows")
def test_wgpu_core_clears_and_draws_real_win32_surface() -> None:
    native = importlib.import_module("_swirui_native")
    backend = Win32PlatformBackend()
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI wgpu CI Smoke", 640, 420))
    backend.show_window(handle)
    backend.poll_events()

    try:
        adapter_name, graphics_backend = native.clear_win32_surface(
            handle.value,
            640,
            420,
            0.027,
            0.043,
            0.078,
            1.0,
        )
        assert adapter_name
        assert graphics_backend

        adapter_name, graphics_backend, rectangle_count = native.draw_rectangles_win32_surface(
            handle.value,
            640,
            420,
            [
                (32.0, 36.0, 260.0, 120.0, 0.0, 0.55, 1.0, 1.0, 28.0, 28.0, 28.0, 28.0),
                (330.0, 80.0, 180.0, 220.0, 0.10, 0.18, 0.34, 0.92, 12.0, 30.0, 18.0, 24.0),
                (96.0, 230.0, 380.0, 96.0, 0.42, 0.18, 1.0, 0.82, 32.0, 8.0, 32.0, 8.0),
            ],
            0.027,
            0.043,
            0.078,
            1.0,
        )
        assert adapter_name
        assert graphics_backend
        assert rectangle_count == 3
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="Persistent GPU test requires Windows")
def test_persistent_wgpu_renderer_draws_shaped_text_and_survives_resize() -> None:
    native = importlib.import_module("_swirui_native")
    backend = Win32PlatformBackend()
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI Persistent GPU Text", 640, 420))
    backend.show_window(handle)
    backend.poll_events()

    try:
        renderer = native.Win32GpuRenderer(handle.value, 640, 420)
        assert renderer.adapter_name
        assert renderer.graphics_backend
        assert renderer.width == 640
        assert renderer.height == 420

        rectangles = [
            (28.0, 34.0, 584.0, 150.0, 0.04, 0.11, 0.20, 1.0, 24.0, 24.0, 24.0, 24.0),
            (28.0, 214.0, 584.0, 150.0, 0.10, 0.18, 0.34, 0.92, 18.0, 30.0, 18.0, 26.0),
        ]
        texts = [
            ("SwirUI GPU text", 56.0, 62.0, 520.0, 52.0, 32.0, 0.92, 0.97, 1.0, 1.0, "Segoe UI"),
            ("Shaping: Zażółć gęślą jaźń ✓", 56.0, 116.0, 520.0, 48.0, 22.0, 0.35, 0.78, 1.0, 1.0, "Segoe UI"),
            ("persistent glyph atlas", 56.0, 246.0, 520.0, 48.0, 26.0, 0.48, 0.90, 0.78, 1.0, "Segoe UI"),
        ]

        assert renderer.draw_scene(rectangles, texts) == (2, 3)
        assert renderer.draw_scene(rectangles, texts) == (2, 3)

        backend.resize_window(handle, 720, 460)
        backend.poll_events()
        renderer.resize(720, 460)
        assert renderer.width == 720
        assert renderer.height == 460
        assert renderer.draw_scene(rectangles, texts) == (2, 3)
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="SceneGraph GPU text test requires Windows")
def test_scenegraph_text_reaches_real_wgpu_renderer() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 680, 440),
    )
    root.add(
        SceneNode(
            key="panel",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(36, 42, 608, 350),
            fill=Color.from_hex("#101B30"),
            corner_radius=CornerRadius.uniform(28),
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(70, 82, 520, 64),
            text="SwirUI — native GPU text",
            fill=Color.from_hex("#EAF7FF"),
            font_size=32,
            font_family="Segoe UI",
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(70, 154, 520, 52),
            text="SceneGraph → Python → Rust → glyphon",
            fill=Color.from_hex("#58C7FF"),
            font_size=21,
            font_family="Segoe UI",
        ),
    )

    renderer = WgpuRenderer()
    app = App("SwirUI GPU Text Integration", renderer=renderer)
    window = Window(title="SwirUI SceneGraph GPU Text", width=680, height=440)
    window.set_scene(Scene(680, 440, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 2
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
