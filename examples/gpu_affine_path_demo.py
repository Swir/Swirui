"""Native retained-affine Path2D demo for the SwirUI Rust/wgpu renderer.

Build and install the native module from ``native/`` before running this example.
The transformed path is rendered on the GPU; rectangle, text and image raster
transforms intentionally remain gated until their native affine pipelines land.
"""

from __future__ import annotations

import math

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
from swirui.rendering.affine import Affine2D

WIDTH = 1120
HEIGHT = 700

root = SceneNode(
    "background",
    SceneNodeKind.GROUP,
    Rect(0, 0, WIDTH, HEIGHT),
    fill=Color.from_hex("#070B14"),
    hit_testable=False,
)
root.add(
    SceneNode(
        "title",
        SceneNodeKind.TEXT,
        Rect(70, 54, 960, 64),
        text="SwirUI — retained affine Path2D",
        fill=Color.from_hex("#EAF7FF"),
        font_size=40,
        hit_testable=False,
    ),
    SceneNode(
        "subtitle",
        SceneNodeKind.TEXT,
        Rect(70, 120, 960, 44),
        text="SceneGraph transform → PyO3 affine payload → persistent Rust/wgpu shader",
        fill=Color.from_hex("#62E5FF"),
        font_size=19,
        hit_testable=False,
    ),
)

clip_layer = SceneNode(
    "translated-clip",
    SceneNodeKind.GROUP,
    Rect(170, 205, 760, 390),
    clip_to_bounds=True,
    hit_testable=False,
    transform=Affine2D.translation(10.0, 8.0),
)
clip_layer.add(
    SceneNode(
        "rotated-concave-path",
        SceneNodeKind.PATH,
        Rect(315, 265, 470, 270),
        fill=Color.from_hex("#0088FF"),
        opacity=0.92,
        path=Path2D.polygon(
            Point(0, 0),
            Point(470, 0),
            Point(470, 90),
            Point(210, 90),
            Point(210, 270),
            Point(0, 270),
        ),
        transform=Affine2D.rotation(
            math.radians(18.0),
            origin=Point(550.0, 400.0),
        ),
    )
)
root.add(clip_layer)

window = Window(title="SwirUI — Affine GPU Path", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI Affine GPU Path Demo",
    config=AppConfig(target_fps=120),
    renderer=WgpuRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
