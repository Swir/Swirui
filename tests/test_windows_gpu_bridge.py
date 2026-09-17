import importlib
import sys

import pytest

from swirui import App, Window
from swirui.platforms import NativeWindowSpec
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


def _isolated_backend(label: str) -> Win32PlatformBackend:
    """Use a unique Win32 class for each in-process native smoke lifecycle."""

    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.NativeSmoke.{label}.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU bridge test requires Windows")
def test_wgpu_core_clears_and_draws_real_win32_surface() -> None:
    native = importlib.import_module("_swirui_native")
    backend = _isolated_backend("stateless")
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
                (
                    330.0,
                    80.0,
                    180.0,
                    220.0,
                    0.10,
                    0.18,
                    0.34,
                    0.92,
                    12.0,
                    30.0,
                    18.0,
                    24.0,
                ),
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


def _checker_rgba() -> bytes:
    return bytes(
        [
            0,
            140,
            255,
            255,
            122,
            46,
            255,
            255,
            122,
            46,
            255,
            255,
            0,
            140,
            255,
            255,
        ]
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Persistent GPU test requires Windows")
def test_persistent_wgpu_renderer_draws_text_images_clips_and_survives_resize() -> None:
    native = importlib.import_module("_swirui_native")
    backend = _isolated_backend("persistent")
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI Persistent GPU Scene", 640, 420))
    backend.show_window(handle)
    backend.poll_events()

    try:
        renderer = native.Win32GpuRenderer(handle.value, 640, 420)
        assert renderer.adapter_name
        assert renderer.graphics_backend
        assert renderer.width == 640
        assert renderer.height == 420
        assert renderer.offscreen_size == (640, 420)
        assert renderer.postprocess_blur_radius == 0.0
        assert renderer.blur_target_size is None
        assert renderer.blur_generation is None
        initial_offscreen_generation = renderer.offscreen_generation
        assert initial_offscreen_generation >= 1
        initial_rectangle_capacity = renderer.rectangle_capacity
        initial_image_capacity = renderer.image_vertex_capacity
        assert initial_rectangle_capacity >= 2
        assert initial_image_capacity >= 1

        renderer.register_image_rgba("checker", 2, 2, _checker_rgba())
        assert renderer.image_resource_count == 1
        assert renderer.image_resource_size("checker") == (2, 2)

        rectangles = [
            (
                28.0,
                34.0,
                584.0,
                150.0,
                0.04,
                0.11,
                0.20,
                1.0,
                24.0,
                24.0,
                24.0,
                24.0,
                44.0,
                48.0,
                596.0,
                176.0,
            ),
            (
                28.0,
                214.0,
                584.0,
                150.0,
                0.10,
                0.18,
                0.34,
                0.92,
                18.0,
                30.0,
                18.0,
                26.0,
                28.0,
                214.0,
                612.0,
                364.0,
            ),
        ]
        texts = [
            (
                "SwirUI GPU text",
                56.0,
                62.0,
                520.0,
                52.0,
                32.0,
                0.92,
                0.97,
                1.0,
                1.0,
                "Segoe UI",
                (80.0, 62.0, 500.0, 114.0),
            ),
            (
                "Shaping: Zażółć gęślą jaźń ✓",
                56.0,
                116.0,
                520.0,
                48.0,
                22.0,
                0.35,
                0.78,
                1.0,
                1.0,
                "Segoe UI",
                (56.0, 116.0, 576.0, 164.0),
            ),
        ]
        images = [
            (
                "checker",
                410.0,
                236.0,
                150.0,
                104.0,
                0.95,
                (438.0, 250.0, 540.0, 320.0),
            )
        ]

        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)
        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)
        assert renderer.offscreen_generation == initial_offscreen_generation
        assert renderer.rectangle_capacity == initial_rectangle_capacity
        assert renderer.image_vertex_capacity == initial_image_capacity

        renderer.set_postprocess_blur_radius(12.0)
        assert renderer.postprocess_blur_radius == 12.0
        assert renderer.blur_target_size == (640, 420)
        initial_blur_generation = renderer.blur_generation
        assert initial_blur_generation is not None
        assert initial_blur_generation >= 1
        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)
        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)
        assert renderer.blur_generation == initial_blur_generation

        many_rectangles = rectangles * (initial_rectangle_capacity // len(rectangles) + 2)
        assert len(many_rectangles) > initial_rectangle_capacity
        assert renderer.draw_scene(many_rectangles, texts, images) == (
            len(many_rectangles),
            2,
            1,
        )
        grown_rectangle_capacity = renderer.rectangle_capacity
        assert grown_rectangle_capacity >= len(many_rectangles)
        assert grown_rectangle_capacity > initial_rectangle_capacity

        many_images = images * (initial_image_capacity + 1)
        assert len(many_images) > initial_image_capacity
        assert renderer.draw_scene(rectangles, texts, many_images) == (
            2,
            2,
            len(many_images),
        )
        grown_image_capacity = renderer.image_vertex_capacity
        assert grown_image_capacity >= len(many_images)
        assert grown_image_capacity > initial_image_capacity

        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)
        assert renderer.offscreen_generation == initial_offscreen_generation
        assert renderer.blur_generation == initial_blur_generation
        assert renderer.rectangle_capacity == grown_rectangle_capacity
        assert renderer.image_vertex_capacity == grown_image_capacity

        backend.resize_window(handle, 720, 460)
        backend.poll_events()
        renderer.resize(720, 460)
        assert renderer.width == 720
        assert renderer.height == 460
        assert renderer.offscreen_size == (720, 460)
        assert renderer.blur_target_size == (720, 460)
        assert renderer.offscreen_generation == initial_offscreen_generation + 1
        assert renderer.blur_generation == initial_blur_generation + 1
        resized_offscreen_generation = renderer.offscreen_generation
        resized_blur_generation = renderer.blur_generation
        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)
        assert renderer.rectangle_capacity == grown_rectangle_capacity
        assert renderer.image_vertex_capacity == grown_image_capacity

        renderer.resize(720, 460)
        assert renderer.offscreen_generation == resized_offscreen_generation
        assert renderer.blur_generation == resized_blur_generation
        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)

        renderer.set_postprocess_blur_radius(0.0)
        assert renderer.postprocess_blur_radius == 0.0
        assert renderer.blur_target_size == (720, 460)
        assert renderer.blur_generation == resized_blur_generation
        assert renderer.draw_scene(rectangles, texts, images) == (2, 2, 1)

        assert renderer.unregister_image("checker") is True
        assert renderer.image_resource_count == 0
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="SceneGraph GPU test requires Windows")
def test_scenegraph_clipped_text_and_image_reach_real_wgpu_renderer() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 680, 440),
    )
    panel = SceneNode(
        key="panel",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(36, 42, 608, 350),
        fill=Color.from_hex("#101B30"),
        corner_radius=CornerRadius.uniform(28),
        clip_to_bounds=True,
    )
    panel.add(
        SceneNode(
            key="preview",
            kind=SceneNodeKind.IMAGE,
            bounds=Rect(10, 228, 300, 180),
            resource_id="checker",
            opacity=0.9,
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(10, 82, 700, 64),
            text="SwirUI — clipped native GPU scene",
            fill=Color.from_hex("#EAF7FF"),
            font_size=32,
            font_family="Segoe UI",
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(70, 154, 520, 52),
            text="SceneGraph → Python → Rust → wgpu",
            fill=Color.from_hex("#58C7FF"),
            font_size=21,
            font_family="Segoe UI",
        ),
    )
    root.add(panel)

    renderer = WgpuRenderer(scene_blur_radius=8.0)
    renderer.register_image_rgba("checker", 2, 2, _checker_rgba())
    backend = _isolated_backend("scenegraph")
    app = App("SwirUI GPU Scene Integration", platform_backend=backend, renderer=renderer)
    window = Window(title="SwirUI SceneGraph GPU Clip", width=680, height=440)
    window.set_scene(Scene(680, 440, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 2
        assert renderer.last_image_count == 1
        assert renderer.image_resource_count == 1
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
