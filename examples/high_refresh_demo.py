"""Display-aware high-refresh SwirUI scene with runtime pacing telemetry."""

from __future__ import annotations

from swirui import App, AppConfig, Window
from swirui.core import Event
from swirui.rendering import Color, CornerRadius, Rect, Scene, SceneNode, SceneNodeKind

CONFIGURED_FPS_CEILING = 240

app = App(
    name="SwirUI High Refresh Demo",
    config=AppConfig(target_fps=CONFIGURED_FPS_CEILING),
)
window = Window(title="SwirUI — display-aware pacing", width=760, height=420)

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
        text="SwirUI display-aware runtime pacing",
        font_size=32,
        fill=Color.from_hex("#DDEEFF"),
    ),
    SceneNode(
        key="subtitle",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(120, 198, 520, 92),
        text="Move this window between monitors: the scheduler follows the active refresh rate.",
        font_size=20,
        fill=Color.from_hex("#78C7FF"),
    ),
)
window.set_scene(Scene(760, 420, root))
app.add_window(window)


def report_display(event: Event) -> None:
    display = event.data["display"]
    target_fps = int(event.data["target_fps"])
    if display is None:
        print(f"display changed: unknown display, target={target_fps} Hz")
        return
    print(
        "display changed: "
        f"{display.name} {display.width}x{display.height} "
        f"scale={display.scale:.2f} refresh={display.refresh_rate_hz:.1f} Hz "
        f"target={target_fps} Hz"
    )


def keep_rendering(event: Event) -> None:
    frame_number = int(event.data["frame_number"])
    target_fps = int(event.data["target_fps"])
    smoothed_fps = event.data["smoothed_fps"]
    if frame_number % max(1, target_fps) == 0 and smoothed_fps is not None:
        refresh_rate = event.data["display_refresh_rate_hz"]
        print(
            f"frame={frame_number} target={target_fps} "
            f"display_refresh={refresh_rate} smoothed_fps={float(smoothed_fps):.1f}"
        )
    app.invalidate(window)


app.on("window_target_fps_changed", report_display)
app.on("frame_rendered", keep_rendering)
raise SystemExit(app.run())
