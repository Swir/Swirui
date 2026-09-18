"""Native retained-affine geometry demo for the SwirUI Rust/wgpu renderer.

Build and install the native module from ``native/`` before running this example.
The transformed Path2D and rounded rectangle render through the GPU affine shape
pipeline. Shaped-text/image transforms and rotated clips intentionally remain
gated until those native compositor slices land.
"""

from __future__ import annotations

import math

from swirui import App, AppConfig, Window
from swirui.rendering import (
    Color,
    CornerRadius,
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
        text="SwirUI — retained affine GPU geometry",
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
    Rect(110, 205, 900, 390),
    clip_to_bounds=True,
    hit_testable=False,
    transform=Affine2D.translation(10.0, 8.0),
)
clip_layer.add(
    SceneNode(
        "rotated-concave-path",
        SceneNodeKind.PATH,
        Rect(185, 285, 370, 220),
        fill=Color.from_hex("#0088FF"),
        opacity=0.92,
        path=Path2D.polygon(
            Point(0, 0),
            Point(370, 0),
            Point(370, 72),
            Point(165, 72),
            Point(165, 220),
            Point(0, 220),
        ),
        transform=Affine2D.rotation(
            math.radians(18.0),
            origin=Point(370.0, 395.0),
        ),
    ),
    SceneNode(
        "rotated-rounded-rectangle",
        SceneNodeKind.RECTANGLE,
        Rect(650, 290, 230, 160),
        fill=Color.from_hex("#62E5FF"),
        opacity=0.92,
        corner_radius=CornerRadius(42.0, 28.0, 18.0, 8.0),
        transform=Affine2D.rotation(
            math.radians(-16.0),
            origin=Point(765.0, 370.0),
        ),
    ),
)
root.add(clip_layer)

window = Window(title="SwirUI — Affine GPU Geometry", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

app = App(
    "SwirUI Affine GPU Geometry Demo",
    config=AppConfig(target_fps=120),
    renderer=WgpuRenderer(),
)
app.add_window(window)
raise SystemExit(app.run())
