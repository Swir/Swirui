"""SwirUI scene rendered by the Rust/wgpu backend on Windows.

Build and install the native module from ``native/`` before running this example.
The demo exercises persistent GPU rendering, per-corner radii and anti-aliased
rounded rectangles directly in WGSL.
"""

from swirui import App, AppConfig, Window
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

WIDTH = 1180
HEIGHT = 760

root = SceneNode(
    "background",
    SceneNodeKind.GROUP,
    Rect(0, 0, WIDTH, HEIGHT),
    fill=Color.from_hex("#070B14"),
)

root.add(
    SceneNode(
        "left-rail",
        SceneNodeKind.RECTANGLE,
        Rect(34, 34, 10, 692),
        fill=Color.from_hex("#00A8FF"),
        corner_radius=CornerRadius.uniform(5),
    ),
    SceneNode(
        "hero",
        SceneNodeKind.RECTANGLE,
        Rect(72, 54, 1038, 250),
        fill=Color.from_hex("#101B30"),
        corner_radius=CornerRadius(30, 30, 22, 22),
    ),
    SceneNode(
        "hero-accent",
        SceneNodeKind.RECTANGLE,
        Rect(102, 88, 430, 12),
        fill=Color.from_hex("#00A8FF"),
        corner_radius=CornerRadius.uniform(6),
    ),
    SceneNode(
        "hero-line-one",
        SceneNodeKind.RECTANGLE,
        Rect(102, 132, 760, 38),
        fill=Color.from_hex("#EAF7FF"),
        corner_radius=CornerRadius.uniform(12),
    ),
    SceneNode(
        "hero-line-two",
        SceneNodeKind.RECTANGLE,
        Rect(102, 190, 560, 18),
        fill=Color.from_hex("#58C7FF"),
        opacity=0.88,
        corner_radius=CornerRadius.uniform(9),
    ),
    SceneNode(
        "status-chip",
        SceneNodeKind.RECTANGLE,
        Rect(102, 244, 190, 32),
        fill=Color.from_hex("#074669"),
        corner_radius=CornerRadius.uniform(16),
    ),
    SceneNode(
        "card-one",
        SceneNodeKind.RECTANGLE,
        Rect(72, 344, 315, 310),
        fill=Color.from_hex("#0D1627"),
        corner_radius=CornerRadius(26, 26, 18, 26),
    ),
    SceneNode(
        "card-two",
        SceneNodeKind.RECTANGLE,
        Rect(432, 344, 315, 310),
        fill=Color.from_hex("#10182C"),
        corner_radius=CornerRadius.uniform(30),
    ),
    SceneNode(
        "card-three",
        SceneNodeKind.RECTANGLE,
        Rect(792, 344, 318, 310),
        fill=Color.from_hex("#0D1627"),
        corner_radius=CornerRadius(26, 18, 26, 26),
    ),
    SceneNode(
        "card-one-accent",
        SceneNodeKind.RECTANGLE,
        Rect(102, 378, 128, 8),
        fill=Color.from_hex("#00A8FF"),
        corner_radius=CornerRadius.uniform(4),
    ),
    SceneNode(
        "card-two-accent",
        SceneNodeKind.RECTANGLE,
        Rect(462, 378, 128, 8),
        fill=Color.from_hex("#7A5CFF"),
        corner_radius=CornerRadius.uniform(4),
    ),
    SceneNode(
        "card-three-accent",
        SceneNodeKind.RECTANGLE,
        Rect(822, 378, 128, 8),
        fill=Color.from_hex("#19E5C0"),
        corner_radius=CornerRadius.uniform(4),
    ),
)

window = Window(title="SwirUI — Rust/wgpu Rounded Rectangle Pipeline", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI GPU Rounded Rectangle Demo",
    config=AppConfig(target_fps=120),
    renderer=WgpuRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
