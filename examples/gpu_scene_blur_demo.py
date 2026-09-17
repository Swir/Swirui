"""Animate whole-scene separable GPU blur without rebuilding the wgpu context."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, Window
from swirui.core import Event
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

WIDTH = 960
HEIGHT = 620
START = time.monotonic()


def build_scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
        fill=Color.from_hex("#050814"),
    )
    root.add(
        SceneNode(
            key="cyan-block",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(110.0, 105.0, 300.0, 310.0),
            fill=Color.from_hex("#008CFF"),
            corner_radius=CornerRadius.uniform(44.0),
        ),
        SceneNode(
            key="violet-block",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(520.0, 180.0, 250.0, 280.0),
            fill=Color.from_hex("#7A2EFF"),
            corner_radius=CornerRadius.uniform(82.0),
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(180.0, 470.0, 600.0, 62.0),
            text="Persistent Rust + wgpu separable blur",
            fill=Color.from_hex("#F5FBFF"),
            font_size=31.0,
            z_index=2,
        ),
    )
    return Scene(WIDTH, HEIGHT, root)


renderer = WgpuRenderer(scene_blur_radius=2.0)
app = App(
    "SwirUI Persistent GPU Blur",
    config=AppConfig(target_fps=120),
    renderer=renderer,
)
window = Window(title="SwirUI — Persistent GPU Scene Blur", width=WIDTH, height=HEIGHT)
window.set_scene(build_scene())
app.add_window(window)


def animate(_: Event) -> None:
    elapsed = time.monotonic() - START
    radius = 2.0 + (math.sin(elapsed * 0.9) + 1.0) * 5.0
    renderer.set_scene_blur_radius(radius)
    app.invalidate(window)


app.on("frame_rendered", animate)
raise SystemExit(app.run())
