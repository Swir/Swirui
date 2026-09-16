import importlib
import sys

import pytest

from swirui import App, Window
from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Color, PathGeometry, Point, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer


def _path_triangles() -> list[tuple[float, ...]]:
    clip = (20.0, 20.0, 600.0, 380.0)
    color = (0.0, 0.66, 1.0, 0.92)
    return [
        (60.0, 60.0, 260.0, 60.0, 220.0, 160.0, *color, *clip),
        (60.0, 60.0, 220.0, 160.0, 100.0, 200.0, *color, *clip),
        (100.0, 200.0, 220.0, 160.0, 260.0, 260.0, *color, *clip),
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="Native path GPU smoke requires Windows")
def test_native_persistent_wgpu_draws_paths_and_survives_resize() -> None:
    native = importlib.import_module("_swirui_native")
    backend = Win32PlatformBackend()
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI GPU Path Smoke", 640, 420))
    backend.show_window(handle)
    backend.poll_events()

    try:
        renderer = native.Win32GpuRenderer(handle.value, 640, 420)
        initial_capacity = renderer.path_triangle_capacity
        paths = _path_triangles()
        assert initial_capacity >= len(paths)

        assert renderer.draw_scene_with_paths([], [], [], paths) == (0, 0, 0, len(paths))
        assert renderer.draw_scene_with_paths([], [], [], paths) == (0, 0, 0, len(paths))
        assert renderer.path_triangle_capacity == initial_capacity

        many_paths = paths * (initial_capacity // len(paths) + 2)
        assert len(many_paths) > initial_capacity
        assert renderer.draw_scene_with_paths([], [], [], many_paths) == (
            0,
            0,
            0,
            len(many_paths),
        )
        grown_capacity = renderer.path_triangle_capacity
        assert grown_capacity >= len(many_paths)
        assert grown_capacity > initial_capacity

        backend.resize_window(handle, 720, 460)
        backend.poll_events()
        renderer.resize(720, 460)
        assert renderer.draw_scene_with_paths([], [], [], paths) == (0, 0, 0, len(paths))
        assert renderer.path_triangle_capacity == grown_capacity
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="SceneGraph path GPU smoke requires Windows")
def test_scenegraph_concave_path_reaches_real_wgpu_renderer() -> None:
    polygon = PathGeometry.polygon(
        Point(70, 70),
        Point(560, 70),
        Point(560, 170),
        Point(330, 130),
        Point(100, 220),
        Point(70, 170),
    )
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 680, 440),
    )
    clip = SceneNode(
        key="clip",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(50, 50, 580, 280),
        clip_to_bounds=True,
        opacity=0.9,
    )
    clip.add(
        SceneNode(
            key="concave-path",
            kind=SceneNodeKind.PATH,
            bounds=polygon.bounds,
            path=polygon,
            fill=Color.from_hex("#00A8FF"),
            opacity=0.85,
        )
    )
    root.add(clip)

    renderer = WgpuRenderer()
    app = App("SwirUI GPU Path Integration", renderer=renderer)
    window = Window(title="SwirUI SceneGraph GPU Path", width=680, height=440)
    window.set_scene(Scene(680, 440, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_path_count == len(polygon.points) - 2
        assert renderer.last_rectangle_count == 0
        assert renderer.last_text_count == 0
        assert renderer.last_image_count == 0
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
