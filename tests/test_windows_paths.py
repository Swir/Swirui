import importlib
import sys

import pytest

from swirui import App, Window
from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend(label: str) -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.PathSmoke.{label}.{id(backend):x}"
    return backend


def _shape_vertices() -> list[tuple[float, ...]]:
    color = (0.0, 0.55, 1.0, 0.9)
    clip = (40.0, 40.0, 600.0, 380.0)
    points = [
        (90.0, 70.0),
        (280.0, 70.0),
        (280.0, 140.0),
        (165.0, 140.0),
        (165.0, 300.0),
        (90.0, 300.0),
    ]
    triangles = [(0, 1, 2), (0, 2, 3), (5, 0, 3), (3, 4, 5)]
    return [(*points[index], *color, *clip) for triangle in triangles for index in triangle]


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU path smoke requires Windows")
def test_native_wgpu_draws_persistent_filled_paths_and_survives_resize() -> None:
    native = importlib.import_module("_swirui_native")
    backend = _isolated_backend("native")
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI GPU Path Smoke", 640, 420))
    backend.show_window(handle)
    backend.poll_events()

    try:
        renderer = native.Win32GpuRenderer(handle.value, 640, 420)
        initial_capacity = renderer.shape_vertex_capacity
        shapes = _shape_vertices()
        assert initial_capacity >= len(shapes)
        assert renderer.draw_scene_with_paths([], [], [], shapes) == (0, 0, 0, 4)
        assert renderer.draw_scene_with_paths([], [], [], shapes) == (0, 0, 0, 4)
        assert renderer.shape_vertex_capacity == initial_capacity

        backend.resize_window(handle, 720, 460)
        backend.poll_events()
        renderer.resize(720, 460)
        assert renderer.draw_scene_with_paths([], [], [], shapes) == (0, 0, 0, 4)
        assert renderer.shape_vertex_capacity == initial_capacity
    finally:
        backend.destroy_window(handle)
        backend.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="SceneGraph GPU path smoke requires Windows")
def test_scenegraph_concave_path_reaches_real_wgpu_renderer() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 680, 440),
    )
    panel = SceneNode(
        key="panel",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(40, 40, 600, 360),
        fill=Color.from_hex("#101B30"),
        clip_to_bounds=True,
    )
    path = Path2D.polygon(
        Point(0, 0),
        Point(240, 0),
        Point(240, 70),
        Point(105, 70),
        Point(105, 220),
        Point(0, 220),
    )
    panel.add(
        SceneNode(
            key="concave-path",
            kind=SceneNodeKind.PATH,
            bounds=Rect(70, 90, 240, 220),
            fill=Color.from_hex("#008CFF"),
            path=path,
            opacity=0.9,
        ),
        SceneNode(
            key="path-label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(340, 130, 250, 80),
            text="GPU Path2D",
            fill=Color.from_hex("#EAF7FF"),
            font_size=30,
        ),
    )
    root.add(panel)

    renderer = WgpuRenderer()
    backend = _isolated_backend("scenegraph")
    app = App(
        "SwirUI GPU Path Integration",
        platform_backend=backend,
        renderer=renderer,
    )
    window = Window(title="SwirUI SceneGraph Paths", width=680, height=440)
    window.set_scene(Scene(680, 440, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 4
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
