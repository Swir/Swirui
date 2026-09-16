"""Native SwirUI SceneGraph rendered with rounded rectangles and shaped GPU text.

Build and install the native module from ``native/`` before running this example.
The demo exercises the full SceneGraph -> Python -> Rust -> glyphon/wgpu path,
including Unicode shaping and a persistent glyph atlas.
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
        "hero",
        SceneNodeKind.RECTANGLE,
        Rect(54, 54, 1012, 250),
        fill=Color.from_hex("#101B30"),
        corner_radius=CornerRadius(32, 32, 22, 22),
    ),
    SceneNode(
        "hero-accent",
        SceneNodeKind.RECTANGLE,
        Rect(88, 86, 150, 8),
        fill=Color.from_hex("#00A8FF"),
        corner_radius=CornerRadius.uniform(4),
    ),
    SceneNode(
        "title",
        SceneNodeKind.TEXT,
        Rect(88, 116, 900, 68),
        text="SwirUI — native GPU text",
        fill=Color.from_hex("#EAF7FF"),
        font_size=42,
        font_family="Segoe UI",
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(88, 188, 900, 48),
        text="SceneGraph → Python → Rust → glyphon → wgpu",
        fill=Color.from_hex("#58C7FF"),
        font_size=22,
        font_family="Segoe UI",
    ),
    SceneNode(
        "unicode",
        SceneNodeKind.TEXT,
        Rect(88, 242, 900, 42),
        text="Unicode shaping: Zażółć gęślą jaźń ✓",
        fill=Color.from_hex("#8FE7FF"),
        font_size=20,
        font_family="Segoe UI",
    ),
    SceneNode(
        "card-one",
        SceneNodeKind.RECTANGLE,
        Rect(54, 342, 492, 292),
        fill=Color.from_hex("#0D1627"),
        corner_radius=CornerRadius(26, 26, 18, 26),
    ),
    SceneNode(
        "card-two",
        SceneNodeKind.RECTANGLE,
        Rect(574, 342, 492, 292),
        fill=Color.from_hex("#10182C"),
        corner_radius=CornerRadius(26, 18, 26, 26),
    ),
    SceneNode(
        "card-one-title",
        SceneNodeKind.TEXT,
        Rect(88, 382, 420, 50),
        text="Persistent glyph atlas",
        fill=Color.from_hex("#FFFFFF"),
        font_size=27,
        font_family="Segoe UI",
    ),
    SceneNode(
        "card-one-copy",
        SceneNodeKind.TEXT,
        Rect(88, 444, 420, 112),
        text="Font shaping and glyph resources live inside the same persistent GPU context.",
        fill=Color.from_hex("#9CCBE5"),
        font_size=18,
        font_family="Segoe UI",
    ),
    SceneNode(
        "card-two-title",
        SceneNodeKind.TEXT,
        Rect(608, 382, 420, 50),
        text="One native scene pass",
        fill=Color.from_hex("#FFFFFF"),
        font_size=27,
        font_family="Segoe UI",
    ),
    SceneNode(
        "card-two-copy",
        SceneNodeKind.TEXT,
        Rect(608, 444, 420, 112),
        text="Rounded rectangles and shaped text are submitted through SwirUI's Rust/wgpu core.",
        fill=Color.from_hex("#A8F0D9"),
        font_size=18,
        font_family="Segoe UI",
    ),
)

window = Window(title="SwirUI — Native GPU Text", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI GPU Text Demo",
    config=AppConfig(target_fps=120),
    renderer=WgpuRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
