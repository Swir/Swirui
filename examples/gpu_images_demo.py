"""Native SwirUI scene with generated RGBA image resources on the GPU.

Build and install the native module from ``native/`` before running this example.
The demo uses generated pixels, so no external image decoder or asset file is
required. It exercises resource registration, persistent texture reuse, image
opacity, rounded rectangles and shaped text in one native wgpu scene.
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
IMAGE_SIZE = 128


def checkerboard_rgba8(size: int) -> bytes:
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            bright = ((x // 16) + (y // 16)) % 2 == 0
            if bright:
                pixels.extend((40, 210, 255, 255))
            else:
                pixels.extend((255, 70, 170, 255))
    return bytes(pixels)


renderer = WgpuRenderer()
renderer.register_image_rgba8(
    "demo-checker",
    IMAGE_SIZE,
    IMAGE_SIZE,
    checkerboard_rgba8(IMAGE_SIZE),
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
        fill=Color.from_hex("#101B30"),
        corner_radius=CornerRadius.uniform(32),
    ),
    SceneNode(
        "title",
        SceneNodeKind.TEXT,
        Rect(88, 92, 900, 64),
        text="SwirUI — persistent GPU images",
        fill=Color.from_hex("#EAF7FF"),
        font_size=40,
        font_family="Segoe UI",
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(88, 158, 900, 42),
        text="SceneGraph → Python resource registry → Rust texture cache → wgpu",
        fill=Color.from_hex("#58C7FF"),
        font_size=20,
        font_family="Segoe UI",
    ),
    SceneNode(
        "image-full",
        SceneNodeKind.IMAGE,
        Rect(110, 242, 280, 280),
        resource_id="demo-checker",
    ),
    SceneNode(
        "image-soft",
        SceneNodeKind.IMAGE,
        Rect(438, 242, 280, 280),
        resource_id="demo-checker",
        opacity=0.55,
    ),
    SceneNode(
        "copy",
        SceneNodeKind.TEXT,
        Rect(764, 250, 240, 230),
        text="One RGBA8 upload is reused by multiple image nodes across frames.",
        fill=Color.from_hex("#B9D8EA"),
        font_size=22,
        font_family="Segoe UI",
    ),
    SceneNode(
        "footer",
        SceneNodeKind.TEXT,
        Rect(110, 566, 860, 42),
        text="No Pillow required — the renderer consumes validated raw RGBA8 resources.",
        fill=Color.from_hex("#9DEFD9"),
        font_size=19,
        font_family="Segoe UI",
    ),
)

window = Window(title="SwirUI — Native GPU Images", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI GPU Images Demo",
    config=AppConfig(target_fps=120),
    renderer=renderer,
)
app.add_window(window)
raise SystemExit(app.run())
