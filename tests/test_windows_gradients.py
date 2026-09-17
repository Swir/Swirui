import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    LinearGradient,
    MeshGradient,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.GradientSmoke.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU gradient smoke requires Windows")
def test_linear_gradient_scene_reaches_real_persistent_wgpu_path_batch() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 720, 460),
        fill=Color.from_hex("#070B14"),
    )
    gradient = LinearGradient.two_color(
        Color.from_hex("#00C2FF"),
        Color.from_hex("#A855F7"),
        start=Point(0.0, 0.5),
        end=Point(1.0, 0.5),
    )
    root.add(
        gradient.to_scene_node("gradient-panel", Rect(70, 70, 580, 260), steps=64),
        SceneNode(
            key="gradient-title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(120, 165, 480, 70),
            text="SwirUI GPU Gradient",
            fill=Color.from_hex("#FFFFFF"),
            font_size=32,
            z_index=2,
        ),
    )

    renderer = WgpuRenderer()
    app = App(
        "SwirUI Gradient Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Gradient Smoke", width=720, height=460)
    window.set_scene(Scene(720, 460, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 128
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU mesh gradient smoke requires Windows")
def test_mesh_gradient_scene_reaches_real_persistent_wgpu_path_batch() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 760, 480),
        fill=Color.from_hex("#070B14"),
    )
    mesh = MeshGradient(
        (
            (
                Color.from_hex("#00E5FF"),
                Color.from_hex("#2563EB"),
                Color.from_hex("#7C3AED"),
            ),
            (
                Color.from_hex("#0F172A"),
                Color.from_hex("#4F46E5"),
                Color.from_hex("#EC4899"),
            ),
            (
                Color.from_hex("#111827"),
                Color.from_hex("#0EA5E9"),
                Color.from_hex("#8B5CF6"),
            ),
        )
    )
    root.add(
        mesh.to_scene_node("mesh-panel", Rect(80, 70, 600, 300), subdivisions=4),
        SceneNode(
            key="mesh-title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(130, 170, 500, 70),
            text="SwirUI GPU Mesh Gradient",
            fill=Color.from_hex("#FFFFFF"),
            font_size=31,
            z_index=2,
        ),
    )

    renderer = WgpuRenderer()
    app = App(
        "SwirUI Mesh Gradient Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Mesh Gradient Smoke", width=760, height=480)
    window.set_scene(Scene(760, 480, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 1
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 128
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
