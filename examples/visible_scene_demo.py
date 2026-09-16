"""First visible SwirUI scene rendered into a real Win32 window.

This example uses the temporary GDI bring-up renderer. The scene API is renderer-neutral and will
remain usable when the final wgpu renderer replaces the preview backend.
"""

from swirui import App, AppConfig, Window
from swirui.rendering import (
    Color,
    CornerRadius,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    Win32PreviewRenderer,
)

WIDTH = 1100
HEIGHT = 720

root = SceneNode(
    "background",
    SceneNodeKind.GROUP,
    Rect(0, 0, WIDTH, HEIGHT),
    fill=Color.from_hex("#070B14"),
)

root.add(
    SceneNode(
        "accent-rail",
        SceneNodeKind.RECTANGLE,
        Rect(38, 38, 8, 644),
        fill=Color.from_hex("#00A8FF"),
        corner_radius=CornerRadius.uniform(4),
    ),
    SceneNode(
        "hero-card",
        SceneNodeKind.RECTANGLE,
        Rect(74, 54, 952, 278),
        fill=Color.from_hex("#101A2D"),
        corner_radius=CornerRadius.uniform(30),
    ),
    SceneNode(
        "hero-title",
        SceneNodeKind.TEXT,
        Rect(112, 98, 700, 60),
        text="SWIRUI // FUTURE INTERFACE",
        fill=Color.from_hex("#F4FAFF"),
        font_size=42,
        font_family="Segoe UI Variable Display",
    ),
    SceneNode(
        "hero-subtitle",
        SceneNodeKind.TEXT,
        Rect(114, 166, 760, 36),
        text="Native window. Renderer-neutral scene. GPU core incoming.",
        fill=Color.from_hex("#71C9FF"),
        font_size=22,
        font_family="Segoe UI Variable Text",
    ),
    SceneNode(
        "status-pill",
        SceneNodeKind.RECTANGLE,
        Rect(114, 238, 212, 52),
        fill=Color.from_hex("#043A55"),
        corner_radius=CornerRadius.uniform(26),
    ),
    SceneNode(
        "status-text",
        SceneNodeKind.TEXT,
        Rect(142, 249, 180, 28),
        text="0.2 ALPHA // LIVE",
        fill=Color.from_hex("#7DDBFF"),
        font_size=20,
        font_family="Segoe UI Semibold",
    ),
    SceneNode(
        "card-one",
        SceneNodeKind.RECTANGLE,
        Rect(74, 364, 294, 252),
        fill=Color.from_hex("#0D1524"),
        corner_radius=CornerRadius.uniform(26),
    ),
    SceneNode(
        "card-two",
        SceneNodeKind.RECTANGLE,
        Rect(403, 364, 294, 252),
        fill=Color.from_hex("#0D1524"),
        corner_radius=CornerRadius.uniform(26),
    ),
    SceneNode(
        "card-three",
        SceneNodeKind.RECTANGLE,
        Rect(732, 364, 294, 252),
        fill=Color.from_hex("#0D1524"),
        corner_radius=CornerRadius.uniform(26),
    ),
    SceneNode(
        "card-one-title",
        SceneNodeKind.TEXT,
        Rect(106, 397, 220, 34),
        text="NATIVE",
        fill=Color.from_hex("#FFFFFF"),
        font_size=24,
        font_family="Segoe UI Semibold",
    ),
    SceneNode(
        "card-one-body",
        SceneNodeKind.TEXT,
        Rect(106, 454, 230, 28),
        text="Win32 HWND online",
        fill=Color.from_hex("#7DDBFF"),
        font_size=18,
    ),
    SceneNode(
        "card-two-title",
        SceneNodeKind.TEXT,
        Rect(435, 397, 220, 34),
        text="SCENE",
        fill=Color.from_hex("#FFFFFF"),
        font_size=24,
        font_family="Segoe UI Semibold",
    ),
    SceneNode(
        "card-two-body",
        SceneNodeKind.TEXT,
        Rect(435, 454, 230, 28),
        text="Retained graph online",
        fill=Color.from_hex("#7DDBFF"),
        font_size=18,
    ),
    SceneNode(
        "card-three-title",
        SceneNodeKind.TEXT,
        Rect(764, 397, 220, 34),
        text="GPU",
        fill=Color.from_hex("#FFFFFF"),
        font_size=24,
        font_family="Segoe UI Semibold",
    ),
    SceneNode(
        "card-three-body",
        SceneNodeKind.TEXT,
        Rect(764, 454, 230, 28),
        text="wgpu core next",
        fill=Color.from_hex("#7DDBFF"),
        font_size=18,
    ),
)

scene = Scene(WIDTH, HEIGHT, root)
window = Window(title="SwirUI — First Visible Scene", width=WIDTH, height=HEIGHT)
window.set_scene(scene)

app = App(
    "SwirUI Visible Scene Demo",
    config=AppConfig(target_fps=120),
    renderer=Win32PreviewRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
