"""Native SwirUI demo for filled convex and concave GPU paths.

Build and install the native module from ``native/`` before running this example.
"""

from swirui import App, AppConfig, Window
from swirui.rendering import (
    Color,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

WIDTH = 1120
HEIGHT = 700

root = SceneNode(
    "background",
    SceneNodeKind.GROUP,
    Rect(0, 0, WIDTH, HEIGHT),
    fill=Color.from_hex("#070B14"),
)
root.add(
    SceneNode(
        "title",
        SceneNodeKind.TEXT,
        Rect(70, 54, 960, 64),
        text="SwirUI — native GPU Path2D",
        fill=Color.from_hex("#EAF7FF"),
        font_size=40,
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(70, 120, 960, 44),
        text=(
            "Concave polygon tessellation → Python bridge → persistent "
            "Rust/wgpu triangle pipeline"
        ),
        fill=Color.from_hex("#58C7FF"),
        font_size=19,
    ),
    SceneNode(
        "triangle",
        SceneNodeKind.PATH,
        Rect(90, 230, 280, 300),
        fill=Color.from_hex("#00A8FF"),
        path=Path2D.polygon(Point(140, 0), Point(280, 300), Point(0, 300)),
    ),
    SceneNode(
        "concave",
        SceneNodeKind.PATH,
        Rect(455, 210, 500, 330),
        fill=Color.from_hex("#7A2EFF"),
        opacity=0.9,
        path=Path2D.polygon(
            Point(0, 0),
            Point(500, 0),
            Point(500, 100),
            Point(205, 100),
            Point(205, 330),
            Point(0, 330),
        ),
    ),
    SceneNode(
        "label",
        SceneNodeKind.TEXT,
        Rect(455, 565, 500, 50),
        text="Simple concave paths are ear-clipped once per prepared frame.",
        fill=Color.from_hex("#BFEAFF"),
        font_size=20,
    ),
)

window = Window(title="SwirUI — GPU Paths", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI GPU Path Demo",
    config=AppConfig(target_fps=120),
    renderer=WgpuRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
