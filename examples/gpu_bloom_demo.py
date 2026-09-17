"""Animate source-driven retained bloom on the persistent native GPU renderer."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, VisualQuality, Window
from swirui.core import Event
from swirui.rendering import (
    Bloom,
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)

WIDTH = 980
HEIGHT = 620
SOURCE_BOUNDS = Rect(230.0, 175.0, 520.0, 270.0)
SOURCE_RADIUS = CornerRadius.uniform(34.0)
QUALITY = VisualQuality.QUALITY
START = time.monotonic()


def build_scene(elapsed: float) -> Scene:
    pulse = 0.62 + (math.sin(elapsed * 2.1) + 1.0) * 0.16
    blur = 30.0 + (math.sin(elapsed * 1.35) + 1.0) * 8.0

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
        fill=Color.from_hex("#040711"),
    )
    root.add(
        Bloom(
            color=Color(0.0, 0.62, 1.0, 0.64),
            blur_radius=blur,
            spread=3.0,
            intensity=pulse,
        )
        .with_quality(QUALITY)
        .to_scene_node(
            "neon-card-bloom",
            SOURCE_BOUNDS,
            corner_radius=SOURCE_RADIUS,
            z_index=-1,
        ),
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=SOURCE_BOUNDS,
            fill=Color.from_hex("#0B1834"),
            corner_radius=SOURCE_RADIUS,
        ),
        SceneNode(
            key="accent",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(270.0, 220.0, 440.0, 5.0),
            fill=Color.from_hex("#00A6FF"),
            corner_radius=CornerRadius.uniform(2.5),
            z_index=2,
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(290.0, 260.0, 400.0, 64.0),
            text="SwirUI Retained Bloom",
            fill=Color.from_hex("#F5FBFF"),
            font_size=36.0,
            z_index=2,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(290.0, 340.0, 400.0, 62.0),
            text=f"{QUALITY.value} · {blur:4.1f} DIP · intensity {pulse:.2f}",
            fill=Color.from_hex("#80D9FF"),
            font_size=20.0,
            z_index=2,
        ),
    )
    return Scene(WIDTH, HEIGHT, root)


app = App(
    "SwirUI Retained Bloom",
    config=AppConfig(target_fps=120, visual_quality=QUALITY),
)
window = Window(
    title="SwirUI — Retained Bloom",
    width=WIDTH,
    height=HEIGHT,
)
window.set_scene(build_scene(0.0))
app.add_window(window)


def animate(_: Event) -> None:
    window.set_scene(build_scene(time.monotonic() - START))
    app.invalidate(window)


app.on("frame_rendered", animate)
raise SystemExit(app.run())
