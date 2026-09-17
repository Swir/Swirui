"""Animate a retained specular reflection sweep through the persistent GPU path pipeline."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, VisualQuality, Window
from swirui.rendering import Color, Rect, Reflection, Scene, SceneNode, SceneNodeKind

WIDTH = 960
HEIGHT = 620
CARD = Rect(210.0, 150.0, 540.0, 320.0)
START = time.monotonic()
CONFIG = AppConfig(target_fps=120, visual_quality=VisualQuality.QUALITY)


def build_scene(elapsed: float) -> Scene:
    position = 0.12 + ((math.sin(elapsed * 1.2) + 1.0) * 0.5) * 0.76
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
        fill=Color.from_hex("#050814"),
    )
    root.add(
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=CARD,
            fill=Color.from_hex("#102E55"),
        ),
        Reflection(
            color=Color(0.72, 0.91, 1.0, 0.34),
            angle_degrees=24.0,
            position=position,
            width=0.16,
        ).with_quality(CONFIG.visual_quality).to_scene_node(
            "card-reflection",
            CARD,
            z_index=1,
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(290.0, 260.0, 380.0, 58.0),
            text="SwirUI Reflection",
            fill=Color.from_hex("#F5FAFF"),
            font_size=36.0,
            z_index=2,
            hit_testable=False,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(300.0, 325.0, 360.0, 46.0),
            text="retained specular sweep · 120 Hz",
            fill=Color.from_hex("#7ED8FF"),
            font_size=18.0,
            z_index=2,
            hit_testable=False,
        ),
    )
    return Scene(WIDTH, HEIGHT, root)


app = App("SwirUI Reflection", config=CONFIG)
window = Window(title="SwirUI — Retained Reflection", width=WIDTH, height=HEIGHT)
window.set_scene(build_scene(0.0))
app.add_window(window)


def animate(_: object) -> None:
    window.set_scene(build_scene(time.monotonic() - START))
    app.invalidate(window)


app.on("frame_rendered", animate)
raise SystemExit(app.run())
