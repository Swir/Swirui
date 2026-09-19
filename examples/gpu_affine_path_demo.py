"""Native retained-affine geometry demo for the SwirUI Rust/wgpu renderer.

Build and install the native module from ``native/`` before running this example.
Transformed Path2D, rounded rectangles and RGBA images render through persistent
native GPU pipelines. Filled geometry also supports exact rotated/sheared
``clip_to_bounds`` regions through deterministic convex clipping. Shaped text
supports positive uniform scale plus translation; text rotation/shear and
non-axis clips for text/images intentionally remain gated until those compositor
slices land.
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
        text="SceneGraph transform → exact affine clips → persistent Rust/wgpu pipelines",
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
        Rect(165, 285, 330, 210),
        fill=Color.from_hex("#0088FF"),
        opacity=0.92,
        path=Path2D.polygon(
            Point(0, 0),
            Point(330, 0),
            Point(330, 70),
            Point(145, 70),
            Point(145, 210),
            Point(0, 210),
        ),
        transform=Affine2D.rotation(
            math.radians(18.0),
            origin=Point(330.0, 390.0),
        ),
    ),
    SceneNode(
        "rotated-rounded-rectangle",
        SceneNodeKind.RECTANGLE,
        Rect(540, 300, 205, 150),
        fill=Color.from_hex("#62E5FF"),
        opacity=0.92,
        corner_radius=CornerRadius(42.0, 28.0, 18.0, 8.0),
        transform=Affine2D.rotation(
            math.radians(-16.0),
            origin=Point(642.5, 375.0),
        ),
    ),
    SceneNode(
        "rotated-image",
        SceneNodeKind.IMAGE,
        Rect(790, 300, 150, 150),
        resource_id="affine-checker",
        opacity=0.96,
        transform=Affine2D.rotation(
            math.radians(22.0),
            origin=Point(865.0, 375.0),
        ),
    ),
    SceneNode(
        "scaled-shaped-text",
        SceneNodeKind.TEXT,
        Rect(305, 515, 500, 54),
        text="glyphon text — retained uniform scale + translation",
        fill=Color.from_hex("#EAF7FF"),
        font_size=24,
        hit_testable=False,
        transform=Affine2D.uniform_scale(
            1.08,
            origin=Point(555.0, 542.0),
        ).then(Affine2D.translation(14.0, -5.0)),
    ),
)
root.add(clip_layer)

rotated_clip = SceneNode(
    "rotated-geometry-clip",
    SceneNodeKind.GROUP,
    Rect(775, 500, 220, 125),
    clip_to_bounds=True,
    hit_testable=False,
    transform=Affine2D.rotation(
        math.radians(14.0),
        origin=Point(885.0, 562.5),
    ),
)
rotated_clip.add(
    SceneNode(
        "exact-clipped-geometry",
        SceneNodeKind.PATH,
        Rect(735, 475, 300, 180),
        fill=Color.from_hex("#35BFFF"),
        opacity=0.82,
        path=Path2D.polygon(
            Point(0, 25),
            Point(300, 0),
            Point(265, 180),
            Point(35, 155),
        ),
    )
)
root.add(rotated_clip)

window = Window(title="SwirUI — Affine GPU Geometry", width=WIDTH, height=HEIGHT)
window.set_scene(Scene(WIDTH, HEIGHT, root))

renderer = WgpuRenderer()
renderer.register_image_rgba(
    "affine-checker",
    2,
    2,
    bytes(
        [
            0,
            136,
            255,
            255,
            98,
            229,
            255,
            255,
            98,
            229,
            255,
            255,
            0,
            136,
            255,
            255,
        ]
    ),
)
app = App(
    "SwirUI Affine GPU Geometry Demo",
    config=AppConfig(target_fps=120),
    renderer=renderer,
)
app.add_window(window)
raise SystemExit(app.run())
