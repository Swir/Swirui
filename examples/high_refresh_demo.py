"""Continuous 144 Hz SwirUI scene demonstrating runtime frame pacing telemetry."""

from __future__ import annotations

from swirui import App, AppConfig, Window
from swirui.core import Event
from swirui.rendering import Color, CornerRadius, Rect, Scene, SceneNode, SceneNodeKind

TARGET_FPS = 144

app = App(
    name="SwirUI High Refresh Demo",
    config=AppConfig(target_fps=TARGET_FPS),
)
window = Window(title="SwirUI — 144 Hz pacing", width=760, height=420)

root = SceneNode(
    key="root",
    kind=SceneNodeKind.GROUP,
    bounds=Rect(0, 0, 760, 420),
)
root.add(
    SceneNode(
        key="panel",
        kind=SceneNodeKind.RECTANGLE,
        bounds=Rect(70, 70, 620, 280),
        fill=Color.from_hex("#10213D"),
        corner_radius=CornerRadius(28, 28, 28, 28),
    ),
    SceneNode(
        key="title",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(118, 118, 520, 58),
        text="SwirUI 144 Hz runtime pacing",
        font_size=34,
        fill=Color.from_hex("#DDEEFF"),
    ),
    SceneNode(
        key="subtitle",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(120, 198, 520, 92),
        text="Deadline-aware idle sleeping keeps the event loop aligned with the next frame.",
        font_size=20,
        fill=Color.from_hex("#78C7FF"),
    ),
)
window.set_scene(Scene(760, 420, root))
app.add_window(window)


def keep_rendering(event: Event) -> None:
    frame_number = int(event.data["frame_number"])
    smoothed_fps = event.data["smoothed_fps"]
    if frame_number % TARGET_FPS == 0 and smoothed_fps is not None:
        print(f"frame={frame_number} smoothed_fps={float(smoothed_fps):.1f}")
    app.invalidate(window)


app.on("frame_rendered", keep_rendering)
raise SystemExit(app.run())
