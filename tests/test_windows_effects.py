import sys

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    CornerRadius,
    DropShadow,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.EffectSmoke.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU shadow smoke requires Windows")
def test_drop_shadow_reaches_real_persistent_wgpu_rectangle_batch() -> None:
    card_bounds = Rect(110.0, 95.0, 500.0, 245.0)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 720.0, 440.0),
    )
    radius = CornerRadius.uniform(28.0)
    root.add(
        DropShadow(
            color=Color(0.1, 0.45, 1.0, 0.4),
            offset=Point(0.0, 16.0),
            blur_radius=30.0,
            spread=3.0,
            steps=12,
        ).to_scene_node("card-shadow", card_bounds, corner_radius=radius),
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=card_bounds,
            fill=Color.from_hex("#101A35"),
            corner_radius=radius,
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(155.0, 175.0, 410.0, 72.0),
            text="SwirUI GPU Shadow",
            fill=Color.from_hex("#FFFFFF"),
            font_size=32.0,
            z_index=2,
        ),
    )

    renderer = WgpuRenderer()
    app = App(
        "SwirUI Shadow Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Shadow Smoke", width=720, height=440)
    window.set_scene(Scene(720.0, 440.0, root))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 13
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 0
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend
    finally:
        app.stop()
