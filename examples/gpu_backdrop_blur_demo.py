"""Animate sharp content behind a retained, rounded GPU backdrop blur panel."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, Window
from swirui.core import Event
from swirui.rendering import (
    BackdropBlur,
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


def build_scene(offset: float = 0.0) -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
    )
    root.add(
        SceneNode(
            key="background",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
            fill=Color.from_hex("#050A18"),
            z_index=0,
        ),
        SceneNode(
            key="cyan-orb",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(120.0 + offset, 135.0, 270.0, 270.0),
            fill=Color.from_hex("#008CFF"),
            corner_radius=CornerRadius.uniform(135.0),
            z_index=1,
        ),
        SceneNode(
            key="violet-orb",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(565.0 - offset * 0.55, 205.0, 225.0, 225.0),
            fill=Color.from_hex("#8B38FF"),
            corner_radius=CornerRadius.uniform(112.5),
            z_index=1,
        ),
    )

    glass = BackdropBlur(
        radius=24.0,
        corner_radius=CornerRadius.uniform(34.0),
    ).to_scene_node(
        "glass",
        Rect(235.0, 150.0, 490.0, 285.0),
        z_index=2,
    )
    glass.add(
        SceneNode(
            key="glass-tint",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(235.0, 150.0, 490.0, 285.0),
            fill=Color(0.04, 0.10, 0.20, 0.42),
            corner_radius=CornerRadius.uniform(34.0),
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(292.0, 238.0, 390.0, 58.0),
            text="SwirUI Backdrop Blur",
            fill=Color.from_hex("#F5FBFF"),
            font_size=34.0,
            z_index=1,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(292.0, 307.0, 390.0, 42.0),
            text="Backdrop soft — foreground sharp",
            fill=Color.from_hex("#B8DFFF"),
            font_size=21.0,
            z_index=2,
        ),
    )
    root.add(glass)
    return Scene(WIDTH, HEIGHT, root)


renderer = WgpuRenderer()
app = App(
    "SwirUI GPU Backdrop Blur",
    config=AppConfig(target_fps=120),
    renderer=renderer,
)
window = Window(title="SwirUI — GPU Backdrop Blur", width=WIDTH, height=HEIGHT)
window.set_scene(build_scene())
app.add_window(window)


def animate(_: Event) -> None:
    elapsed = time.monotonic() - START
    offset = math.sin(elapsed * 1.15) * 115.0
    window.set_scene(build_scene(offset))
    app.invalidate(window)


app.on("frame_rendered", animate)
raise SystemExit(app.run())
