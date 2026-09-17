import sys
import time

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Bloom,
    Color,
    CornerRadius,
    DynamicShadow,
    Glow,
    Noise,
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


def _dynamic_effect_scene(light_direction_degrees: float) -> Scene:
    card_bounds = Rect(110.0, 95.0, 500.0, 245.0)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 720.0, 440.0),
    )
    radius = CornerRadius.uniform(28.0)
    root.add(
        DynamicShadow(
            elevation=20.0,
            color=Color(0.02, 0.12, 0.28, 0.38),
            light_direction_degrees=light_direction_degrees,
            light_altitude_degrees=48.0,
            softness=1.5,
            spread=2.0,
            steps=10,
        ).to_scene_node("card-shadow", card_bounds, corner_radius=radius),
        Glow(
            color=Color(0.0, 0.58, 1.0, 0.26),
            blur_radius=18.0,
            spread=1.0,
            steps=6,
        ).to_scene_node("card-glow", card_bounds, corner_radius=radius),
        Bloom(
            color=Color(0.0, 0.68, 1.0, 0.42),
            blur_radius=28.0,
            spread=2.0,
            intensity=0.72,
            steps=8,
        ).to_scene_node("card-bloom", card_bounds, corner_radius=radius),
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=card_bounds,
            fill=Color.from_hex("#101A35"),
            corner_radius=radius,
        ),
        Noise(
            samples=32,
            size=1.25,
            color=Color(0.82, 0.92, 1.0, 0.08),
            seed=2026,
        ).to_scene_node("card-noise", card_bounds, z_index=1),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(155.0, 175.0, 410.0, 72.0),
            text="SwirUI Dynamic GPU Effects",
            fill=Color.from_hex("#FFFFFF"),
            font_size=32.0,
            z_index=2,
        ),
    )
    return Scene(720.0, 440.0, root)


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU effect smoke requires Windows")
def test_dynamic_shadow_glow_bloom_and_noise_reach_real_persistent_wgpu_batch() -> None:
    renderer = WgpuRenderer()
    app = App(
        "SwirUI Dynamic Effects Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Effects Smoke", width=720, height=440)
    window.set_scene(_dynamic_effect_scene(270.0))
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.last_rectangle_count == 57
        assert renderer.last_text_count == 1
        assert renderer.last_image_count == 0
        assert renderer.last_path_count == 0
        assert renderer.persistent_context_count == 1
        assert renderer.adapter_name
        assert renderer.graphics_backend

        native_handle = window.native_handle
        assert native_handle is not None
        handle = native_handle.value
        first_context = renderer._contexts[handle]

        window.set_scene(_dynamic_effect_scene(180.0))
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1

        assert renderer.frames_rendered == 2
        assert renderer.last_rectangle_count == 57
        assert renderer.persistent_context_count == 1
        assert renderer._contexts[handle] is first_context
    finally:
        app.stop()