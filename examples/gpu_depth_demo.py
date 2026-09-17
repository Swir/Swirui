"""Animate retained perspective with live pointer-driven parallax on the GPU path pipeline."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, Window
from swirui.core import Event
from swirui.rendering import (
    Color,
    Parallax,
    PerspectivePlane,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)

WIDTH = 980
HEIGHT = 640
VIEWPORT = Rect(0.0, 0.0, WIDTH, HEIGHT)
CARD_BOUNDS = Rect(250.0, 170.0, 480.0, 300.0)
START = time.monotonic()
POINTER = Point(WIDTH * 0.5, HEIGHT * 0.5)
PARALLAX = Parallax(
    max_rotation_x_degrees=10.0,
    max_rotation_y_degrees=14.0,
    perspective=920.0,
    depth=28.0,
)


def build_scene(elapsed: float) -> Scene:
    pedestal_depth = 20.0 + (math.sin(elapsed * 0.9) + 1.0) * 24.0

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=VIEWPORT,
        fill=Color.from_hex("#050815"),
    )
    root.add(
        PerspectivePlane(
            rotation_x_degrees=62.0,
            perspective=860.0,
            depth=pedestal_depth,
        ).to_scene_node(
            "pedestal",
            Rect(245.0, 430.0, 490.0, 105.0),
            fill=Color(0.02, 0.38, 0.72, 0.34),
            hit_testable=False,
        ),
        PARALLAX.to_scene_node(
            "parallax-card",
            CARD_BOUNDS,
            pointer=POINTER,
            viewport=VIEWPORT,
            fill=Color.from_hex("#102A56"),
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(330.0, 260.0, 330.0, 58.0),
            text="SwirUI Depth + Parallax",
            fill=Color.from_hex("#F7FBFF"),
            font_size=34.0,
            z_index=2,
            hit_testable=False,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(330.0, 330.0, 340.0, 70.0),
            text=f"live pointer parallax · {POINTER.x:3.0f}, {POINTER.y:3.0f} DIP",
            fill=Color.from_hex("#7ED8FF"),
            font_size=18.0,
            z_index=2,
            hit_testable=False,
        ),
    )
    return Scene(WIDTH, HEIGHT, root)


app = App("SwirUI Depth", config=AppConfig(target_fps=120))
window = Window(title="SwirUI — Retained Depth and Parallax", width=WIDTH, height=HEIGHT)
window.set_scene(build_scene(0.0))
app.add_window(window)


def track_pointer(event: Event) -> None:
    global POINTER
    platform_event = event.data.get("event")
    x = getattr(platform_event, "x", None)
    y = getattr(platform_event, "y", None)
    if x is None or y is None:
        return
    POINTER = Point(float(x), float(y))


def animate(_: Event) -> None:
    window.set_scene(build_scene(time.monotonic() - START))
    app.invalidate(window)


window.on("pointer_move", track_pointer)
app.on("frame_rendered", animate)
raise SystemExit(app.run())
