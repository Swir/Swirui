"""Native SwirUI demo for filled vector paths on the persistent wgpu renderer.

Build and install the native module from ``native/`` before running this example.
The scene demonstrates convex and concave paths, hierarchical clipping, opacity,
Unicode text and logical-DIP geometry rendered through the Rust/wgpu path pipeline.
"""

from swirui import App, AppConfig, Window
from swirui.rendering import (
    Color,
    CornerRadius,
    PathGeometry,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

WIDTH = 1120
HEIGHT = 700


def polygon(*coordinates: tuple[float, float]) -> PathGeometry:
    return PathGeometry.polygon(*(Point(x, y) for x, y in coordinates))


root = SceneNode(
    "background",
    SceneNodeKind.GROUP,
    Rect(0, 0, WIDTH, HEIGHT),
    fill=Color.from_hex("#070B14"),
)
card = SceneNode(
    "card",
    SceneNodeKind.GROUP,
    Rect(54, 54, 1012, 592),
    fill=Color.from_hex("#0D1627"),
    corner_radius=CornerRadius.uniform(32),
    clip_to_bounds=True,
)

chevron = polygon(
    (110, 320),
    (260, 235),
    (440, 320),
    (350, 320),
    (260, 275),
    (185, 320),
)
star = polygon(
    (570, 230),
    (610, 302),
    (694, 315),
    (633, 372),
    (648, 454),
    (570, 414),
    (492, 454),
    (507, 372),
    (446, 315),
    (530, 302),
)
arrow = polygon(
    (765, 250),
    (940, 340),
    (765, 430),
    (810, 340),
)

card.add(
    SceneNode(
        "accent",
        SceneNodeKind.RECTANGLE,
        Rect(88, 88, 150, 8),
        fill=Color.from_hex("#00A8FF"),
        corner_radius=CornerRadius.uniform(4),
    ),
    SceneNode(
        "title",
        SceneNodeKind.TEXT,
        Rect(88, 118, 900, 62),
        text="SwirUI — native GPU vector paths",
        fill=Color.from_hex("#EAF7FF"),
        font_size=40,
        font_family="Segoe UI",
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(88, 182, 900, 42),
        text="SceneGraph PATH → tessellation → Python → Rust → reusable wgpu triangles",
        fill=Color.from_hex("#58C7FF"),
        font_size=19,
        font_family="Segoe UI",
    ),
    SceneNode(
        "chevron",
        SceneNodeKind.PATH,
        chevron.bounds,
        path=chevron,
        fill=Color.from_hex("#00A8FF"),
        opacity=0.92,
    ),
    SceneNode(
        "star",
        SceneNodeKind.PATH,
        star.bounds,
        path=star,
        fill=Color.from_hex("#7A3CFF"),
        opacity=0.88,
    ),
    SceneNode(
        "arrow",
        SceneNodeKind.PATH,
        arrow.bounds,
        path=arrow,
        fill=Color.from_hex("#27D9B5"),
        opacity=0.90,
    ),
    SceneNode(
        "footer",
        SceneNodeKind.TEXT,
        Rect(88, 525, 900, 58),
        text="Concave fills • clip-aware fragments • HiDPI scaling • exact hit testing ✓",
        fill=Color.from_hex("#A8D5EA"),
        font_size=20,
        font_family="Segoe UI",
    ),
)
root.add(card)

renderer = WgpuRenderer()
window = Window(title="SwirUI — Native GPU Paths", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI GPU Path Demo",
    config=AppConfig(target_fps=120),
    renderer=renderer,
)
app.add_window(window)
raise SystemExit(app.run())
