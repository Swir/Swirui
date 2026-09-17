"""Show retained frosted-glass and acrylic materials on the native GPU renderer."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, Window
from swirui.core import Event, VisualQuality
from swirui.rendering import (
    Acrylic,
    Color,
    CornerRadius,
    FrostedGlass,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

WIDTH = 1120
HEIGHT = 680
START = time.monotonic()


def _label(key: str, text: str, bounds: Rect, size: float, *, z_index: int = 10) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.TEXT,
        bounds=bounds,
        text=text,
        fill=Color.from_hex("#F4FAFF"),
        font_size=size,
        z_index=z_index,
    )


def build_scene(offset: float = 0.0) -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
    )
    root.add(
        SceneNode(
            "background",
            SceneNodeKind.RECTANGLE,
            Rect(0.0, 0.0, WIDTH, HEIGHT),
            fill=Color.from_hex("#050914"),
        ),
        SceneNode(
            "cyan-orb",
            SceneNodeKind.RECTANGLE,
            Rect(70.0 + offset, 95.0, 330.0, 330.0),
            fill=Color.from_hex("#008CFF"),
            corner_radius=CornerRadius.uniform(165.0),
            z_index=1,
        ),
        SceneNode(
            "violet-orb",
            SceneNodeKind.RECTANGLE,
            Rect(705.0 - offset * 0.55, 195.0, 290.0, 290.0),
            fill=Color.from_hex("#8C3DFF"),
            corner_radius=CornerRadius.uniform(145.0),
            z_index=1,
        ),
    )

    glass = FrostedGlass(
        blur_radius=22.0,
        corner_radius=CornerRadius.uniform(30.0),
    ).to_scene_node(
        "frosted",
        Rect(95.0, 165.0, 425.0, 300.0),
        z_index=2,
    )
    glass.add(
        _label("frosted-title", "Frosted Glass", Rect(145.0, 250.0, 330.0, 54.0), 32.0),
        _label(
            "frosted-subtitle",
            "Backdrop blur + tint + border",
            Rect(145.0, 315.0, 330.0, 40.0),
            19.0,
            z_index=11,
        ),
    )

    acrylic = Acrylic(
        blur_radius=30.0,
        corner_radius=CornerRadius.uniform(30.0),
    ).with_quality(VisualQuality.QUALITY).to_scene_node(
        "acrylic",
        Rect(600.0, 165.0, 425.0, 300.0),
        z_index=3,
    )
    acrylic.add(
        _label("acrylic-title", "Acrylic", Rect(650.0, 250.0, 325.0, 54.0), 32.0),
        _label(
            "acrylic-subtitle",
            "Tint + luminosity + retained grain",
            Rect(650.0, 315.0, 325.0, 40.0),
            19.0,
            z_index=11,
        ),
    )

    root.add(glass, acrylic)
    return Scene(WIDTH, HEIGHT, root)


renderer = WgpuRenderer()
app = App(
    "SwirUI GPU Glass Materials",
    config=AppConfig(target_fps=120, visual_quality=VisualQuality.QUALITY),
    renderer=renderer,
)
window = Window(title="SwirUI — Frosted Glass + Acrylic", width=WIDTH, height=HEIGHT)
window.set_scene(build_scene())
app.add_window(window)


def animate(_: Event) -> None:
    elapsed = time.monotonic() - START
    offset = math.sin(elapsed * 1.05) * 115.0
    window.set_scene(build_scene(offset))
    app.invalidate(window)


app.on("frame_rendered", animate)
raise SystemExit(app.run())
