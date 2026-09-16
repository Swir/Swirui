"""Native SwirUI SceneGraph rendered with cached RGBA images, text and shapes.

Build and install the native module from ``native/`` before running this example.
The demo registers two small generated RGBA8 resources, uploads them once into the
persistent Rust/wgpu context and reuses those textures while rendering the scene.
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


def checker_rgba(size: int, first: tuple[int, int, int], second: tuple[int, int, int]) -> bytes:
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            red, green, blue = first if (x // 8 + y // 8) % 2 == 0 else second
            pixels.extend((red, green, blue, 255))
    return bytes(pixels)


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
        "image-one",
        SceneNodeKind.IMAGE,
        Rect(88, 92, 168, 168),
        resource_id="cyan-checker",
    ),
    SceneNode(
        "title",
        SceneNodeKind.TEXT,
        Rect(296, 112, 700, 64),
        text="SwirUI — cached GPU images",
        fill=Color.from_hex("#EAF7FF"),
        font_size=39,
        font_family="Segoe UI",
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(296, 184, 700, 50),
        text="Scene resources → Python cache → Rust texture → wgpu",
        fill=Color.from_hex("#58C7FF"),
        font_size=21,
        font_family="Segoe UI",
    ),
    SceneNode(
        "card",
        SceneNodeKind.RECTANGLE,
        Rect(54, 342, 1012, 292),
        fill=Color.from_hex("#0D1627"),
        corner_radius=CornerRadius.uniform(26),
    ),
    SceneNode(
        "image-two",
        SceneNodeKind.IMAGE,
        Rect(88, 382, 184, 184),
        opacity=0.92,
        resource_id="violet-checker",
    ),
    SceneNode(
        "card-title",
        SceneNodeKind.TEXT,
        Rect(314, 388, 650, 52),
        text="Versioned persistent resources",
        fill=Color.from_hex("#FFFFFF"),
        font_size=29,
        font_family="Segoe UI",
    ),
    SceneNode(
        "card-copy",
        SceneNodeKind.TEXT,
        Rect(314, 458, 650, 120),
        text=(
            "Unchanged RGBA payloads stay resident in the native GPU context. "
            "Replacing a resource increments its revision and uploads only the new pixels."
        ),
        fill=Color.from_hex("#A8F0D9"),
        font_size=18,
        font_family="Segoe UI",
    ),
)

scene = Scene(WIDTH, HEIGHT, root)
scene.register_image_rgba8(
    "cyan-checker",
    64,
    64,
    checker_rgba(64, (0, 168, 255), (22, 42, 78)),
)
scene.register_image_rgba8(
    "violet-checker",
    64,
    64,
    checker_rgba(64, (148, 86, 255), (28, 210, 190)),
)

window = Window(title="SwirUI — Native GPU Images", width=WIDTH, height=HEIGHT)
window.set_scene(scene)

app = App(
    "SwirUI GPU Image Demo",
    config=AppConfig(target_fps=120),
    renderer=WgpuRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
