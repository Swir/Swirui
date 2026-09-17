"""Show deterministic retained noise budgets on the native GPU renderer."""

from __future__ import annotations

from swirui import App, AppConfig, Window
from swirui.core import Event, VisualQuality
from swirui.rendering import Color, Noise, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer

WIDTH = 1120
HEIGHT = 660


def _label(key: str, text: str, bounds: Rect, *, z_index: int) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.TEXT,
        bounds=bounds,
        text=text,
        fill=Color.from_hex("#EFF8FF"),
        font_size=22.0,
        z_index=z_index,
    )


def build_scene() -> Scene:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, WIDTH, HEIGHT))
    root.add(
        SceneNode(
            "background",
            SceneNodeKind.RECTANGLE,
            Rect(0.0, 0.0, WIDTH, HEIGHT),
            fill=Color.from_hex("#06101F"),
        )
    )

    profiles = (
        ("Performance", VisualQuality.PERFORMANCE),
        ("Balanced", VisualQuality.BALANCED),
        ("Quality", VisualQuality.QUALITY),
        ("Cinematic", VisualQuality.CINEMATIC),
    )
    base = Noise(size=1.5, color=Color(0.82, 0.92, 1.0, 0.11), seed=2026)

    for index, (name, quality) in enumerate(profiles):
        column = index % 2
        row = index // 2
        x = 80.0 + column * 510.0
        y = 90.0 + row * 270.0
        bounds = Rect(x, y, 450.0, 210.0)
        root.add(
            SceneNode(
                f"panel:{index}",
                SceneNodeKind.RECTANGLE,
                bounds,
                fill=Color(0.035, 0.11, 0.20, 1.0),
                z_index=1,
            ),
            base.with_quality(quality).to_scene_node(
                f"noise:{index}",
                bounds,
                z_index=2,
            ),
            _label(
                f"label:{index}",
                f"{name} — {base.with_quality(quality).samples} grains",
                Rect(x + 28.0, y + 78.0, 390.0, 48.0),
                z_index=3,
            ),
        )

    return Scene(WIDTH, HEIGHT, root)


renderer = WgpuRenderer()
app = App(
    "SwirUI Retained Noise",
    config=AppConfig(target_fps=120, visual_quality=VisualQuality.QUALITY),
    renderer=renderer,
)
window = Window(title="SwirUI — Retained Noise / Grain", width=WIDTH, height=HEIGHT)
window.set_scene(build_scene())
app.add_window(window)


def keep_presenting(_: Event) -> None:
    # Re-render the same retained scene: grain positions are not regenerated per frame.
    app.invalidate(window)


app.on("frame_rendered", keep_presenting)
raise SystemExit(app.run())
