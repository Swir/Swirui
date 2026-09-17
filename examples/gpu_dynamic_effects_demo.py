"""Animate quality-aware elevation shadows while reusing a persistent GPU context."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, VisualQuality, Window
from swirui.core import Event
from swirui.rendering import (
    Color,
    CornerRadius,
    DynamicShadow,
    Glow,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)

WIDTH = 980
HEIGHT = 640
CARD_BOUNDS = Rect(220.0, 170.0, 540.0, 300.0)
CARD_RADIUS = CornerRadius.uniform(34.0)
QUALITY = VisualQuality.QUALITY
START = time.monotonic()


def build_scene(elapsed: float) -> Scene:
    light_direction = 270.0 + math.sin(elapsed * 0.72) * 72.0
    elevation = 18.0 + (math.sin(elapsed * 1.05) + 1.0) * 7.0

    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
        fill=Color.from_hex("#050815"),
    )
    root.add(
        DynamicShadow(
            elevation=elevation,
            color=Color(0.0, 0.08, 0.22, 0.42),
            light_direction_degrees=light_direction,
            light_altitude_degrees=48.0,
            softness=1.55,
            spread=2.0,
        )
        .with_quality(QUALITY)
        .to_scene_node(
            "dynamic-shadow",
            CARD_BOUNDS,
            corner_radius=CARD_RADIUS,
            z_index=-2,
        ),
        Glow(
            color=Color(0.0, 0.58, 1.0, 0.24),
            blur_radius=20.0,
            spread=1.0,
        )
        .with_quality(QUALITY)
        .to_scene_node(
            "card-glow",
            CARD_BOUNDS,
            corner_radius=CARD_RADIUS,
            z_index=-1,
        ),
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=CARD_BOUNDS,
            fill=Color.from_hex("#0E1B39"),
            corner_radius=CARD_RADIUS,
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(285.0, 245.0, 410.0, 62.0),
            text="SwirUI Dynamic Shadows",
            fill=Color.from_hex("#F7FBFF"),
            font_size=36.0,
            z_index=2,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(285.0, 325.0, 410.0, 86.0),
            text=(
                f"{QUALITY.value} quality · elevation {elevation:4.1f} DIP · "
                f"light {light_direction:5.1f}°"
            ),
            fill=Color.from_hex("#7ED8FF"),
            font_size=20.0,
            z_index=2,
        ),
    )
    return Scene(WIDTH, HEIGHT, root)


app = App(
    "SwirUI Dynamic GPU Effects",
    config=AppConfig(target_fps=120, visual_quality=QUALITY),
)
window = Window(
    title="SwirUI — Dynamic Shadows + Glow",
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
