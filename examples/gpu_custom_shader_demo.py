"""Animate a validated custom WGSL effect on SwirUI's persistent GPU renderer."""

from __future__ import annotations

import math
import time

from swirui import App, Window
from swirui.rendering import (
    Color,
    CustomShaderEffect,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

SHADER = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let centered = uv - vec2<f32>(0.5, 0.5);
    let distance_from_center = length(centered);
    let vignette = clamp(1.0 - distance_from_center * params.x, 0.25, 1.0);
    let scanline = 0.88 + 0.12 * sin(uv.y * 180.0 + params.y);
    let shifted = mix(color.rgb, color.bgr, params.z);
    return vec4<f32>(shifted * vignette * scanline, color.a);
}
"""


def scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 900.0, 540.0),
    )
    cards = (
        ("cyan", Rect(90.0, 110.0, 220.0, 220.0), Color(0.0, 0.72, 1.0, 1.0)),
        ("violet", Rect(340.0, 110.0, 220.0, 220.0), Color(0.55, 0.18, 1.0, 1.0)),
        ("orange", Rect(590.0, 110.0, 220.0, 220.0), Color(1.0, 0.34, 0.06, 1.0)),
    )
    for key, bounds, fill in cards:
        root.add(
            SceneNode(
                key=key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                fill=fill,
            )
        )
    root.add(
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(125.0, 385.0, 650.0, 72.0),
            text="SwirUI — persistent custom WGSL post-processing",
            fill=Color(1.0, 1.0, 1.0, 1.0),
            font_size=29.0,
        )
    )
    return Scene(900.0, 540.0, root)


def main() -> None:
    effect = CustomShaderEffect(
        SHADER,
        parameters=(0.65, 0.0, 0.0, 0.0),
        label="animated-cyber-vignette",
    )
    renderer = WgpuRenderer(custom_shader=effect)
    app = App("SwirUI GPU Custom Shader", renderer=renderer)
    window = Window(title="SwirUI — Custom WGSL", width=900, height=540)
    window.set_scene(scene())
    app.add_window(window)
    app.start()

    started = time.monotonic()
    try:
        while window.is_open:
            elapsed = time.monotonic() - started
            channel_swap = 0.25 + 0.25 * (1.0 + math.sin(elapsed * 0.8))
            renderer.set_custom_shader(
                effect.with_parameters(0.65, elapsed * 5.0, channel_swap, 0.0)
            )
            app.invalidate(window)
            app.poll_events()
            app.render_pending()
            time.sleep(1.0 / 120.0)
    finally:
        app.stop()


if __name__ == "__main__":
    main()
