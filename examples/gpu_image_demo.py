"""Native SwirUI scene with persistent GPU image resources.

Build and install the native module from ``native/`` before running this example.
The image is generated in memory so the demo has no external asset dependency.
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
IMAGE_WIDTH = 256
IMAGE_HEIGHT = 180


def make_gradient_rgba(width: int, height: int) -> bytes:
    pixels = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 4
            fx = x / max(width - 1, 1)
            fy = y / max(height - 1, 1)
            pixels[offset] = int(15 + 25 * fy)
            pixels[offset + 1] = int(90 + 130 * fx)
            pixels[offset + 2] = int(170 + 75 * (1.0 - fy))
            pixels[offset + 3] = 255
    return bytes(pixels)


renderer = WgpuRenderer()
renderer.register_image_rgba(
    "demo-gradient",
    IMAGE_WIDTH,
    IMAGE_HEIGHT,
    make_gradient_rgba(IMAGE_WIDTH, IMAGE_HEIGHT),
)

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
        Rect(54, 54, 1012, 592),
        fill=Color.from_hex("#0D1627"),
        corner_radius=CornerRadius.uniform(32),
    ),
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
        text="SwirUI — persistent GPU images",
        fill=Color.from_hex("#EAF7FF"),
        font_size=40,
        font_family="Segoe UI",
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(88, 182, 900, 48),
        text="SceneGraph IMAGE → Python resource registry → Rust texture cache → wgpu",
        fill=Color.from_hex("#58C7FF"),
        font_size=20,
        font_family="Segoe UI",
    ),
    SceneNode(
        "image-frame",
        SceneNodeKind.RECTANGLE,
        Rect(88, 264, 612, 322),
        fill=Color.from_hex("#111E34"),
        corner_radius=CornerRadius.uniform(24),
    ),
    SceneNode(
        "preview",
        SceneNodeKind.IMAGE,
        Rect(116, 292, 556, 266),
        resource_id="demo-gradient",
    ),
    SceneNode(
        "info-title",
        SceneNodeKind.TEXT,
        Rect(744, 292, 270, 44),
        text="RGBA8 texture",
        fill=Color.from_hex("#FFFFFF"),
        font_size=25,
        font_family="Segoe UI",
    ),
    SceneNode(
        "info-copy",
        SceneNodeKind.TEXT,
        Rect(744, 346, 270, 180),
        text=(
            "The texture is uploaded once and reused by the persistent native GPU context. "
            "Resize keeps the resource alive while scene geometry is rebuilt."
        ),
        fill=Color.from_hex("#A8D5EA"),
        font_size=17,
        font_family="Segoe UI",
    ),
)

window = Window(title="SwirUI — Native GPU Images", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI GPU Image Demo",
    config=AppConfig(target_fps=120),
    renderer=renderer,
)
app.add_window(window)
raise SystemExit(app.run())
