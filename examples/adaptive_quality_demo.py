"""Drive quality-aware retained effects from SwirUI's AUTO runtime profile."""

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
START = time.monotonic()

app = App(
    "SwirUI Adaptive Quality",
    config=AppConfig(target_fps=120, visual_quality=VisualQuality.AUTO),
)
window = Window(
    title="SwirUI — Adaptive Visual Quality",
    width=WIDTH,
    height=HEIGHT,
)


def build_scene(elapsed: float, fps: float | None = None) -> Scene:
    quality = app.effective_visual_quality
    light_direction = 270.0 + math.sin(elapsed * 0.72) * 72.0
    elevation = 18.0 + (math.sin(elapsed * 1.05) + 1.0) * 7.0
    fps_label = "warming up" if fps is None else f"{fps:5.1f} FPS"

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
        .with_quality(quality)
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
        .with_quality(quality)
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
            bounds=Rect(285.0, 235.0, 410.0, 62.0),
            text="SwirUI AUTO Quality",
            fill=Color.from_hex("#F7FBFF"),
            font_size=36.0,
            z_index=2,
        ),
        SceneNode(
            key="profile",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(285.0, 315.0, 410.0, 40.0),
            text=f"Profile: {quality.value} · {fps_label}",
            fill=Color.from_hex("#7ED8FF"),
            font_size=20.0,
            z_index=2,
        ),
        SceneNode(
            key="hint",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(285.0, 370.0, 410.0, 64.0),
            text="AUTO uses real render cost + pacing hysteresis",
            fill=Color.from_hex("#A8B9D8"),
            font_size=16.0,
            z_index=2,
        ),
    )
    return Scene(WIDTH, HEIGHT, root)


window.set_scene(build_scene(0.0))
app.add_window(window)


def animate(event: Event) -> None:
    smoothed_fps = event.data.get("smoothed_fps")
    fps = float(smoothed_fps) if isinstance(smoothed_fps, (int, float)) else None
    window.set_scene(build_scene(time.monotonic() - START, fps))
    app.invalidate(window)


def report_quality_change(event: Event) -> None:
    old_quality = event.data["old_quality"]
    new_quality = event.data["quality"]
    reason = event.data["reason"]
    print(f"SwirUI quality: {old_quality.value} -> {new_quality.value} ({reason})")


app.on("frame_rendered", animate)
app.on("visual_quality_changed", report_quality_change)
raise SystemExit(app.run())
