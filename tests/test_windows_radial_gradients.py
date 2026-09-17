import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    Point,
    RadialGradient,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.RadialGradientSmoke.{id(backend):x}"
    return backend


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Native GPU radial gradient smoke needs Windows",
)
def test_radial_gradient_scene_reaches_real_persistent_wgpu_path_batch() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, 720, 460),
        fill=Color.from_hex("#070B14"),
    )
    gradient = RadialGradient.two_color(
        Color.from_hex("#E8FDFF"),
        Color.from_hex("#4338CA"),
        center=Point(0.42, 0.46),
        radius=0.86,
    )
    root.add(
        gradient.to_scene_node(
            "radial-panel",
            Rect(70, 70, 580, 260),
            steps=24,
            segments=32,
        ),
        SceneNode(
            key="radial-title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(120, 165, 480, 70),
            text="SwirUI GPU Radial",
            fill=Color.from_hex("#FFFFFF"),
            font_size=32,
            z_index=2,
        ),
    )

    renderer = WgpuRenderer()
    app = App(
        "SwirUI Radial Gradient Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Radial Gradient Smoke", width=720, height=460)
    window.set_scene(Scene(720, 460, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 2
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 24 * (32 - 2)
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
