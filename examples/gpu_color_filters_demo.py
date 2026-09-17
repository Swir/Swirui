"""Animate composable whole-scene GPU color filters on the persistent wgpu renderer."""

from __future__ import annotations

import math
import time

from swirui import App, Window
from swirui.rendering import (
    Color,
    ColorFilter,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 860.0, 520.0),
    )
    cards = (
        ("cyan", Rect(80.0, 100.0, 210.0, 220.0), Color(0.0, 0.72, 1.0, 1.0)),
        ("violet", Rect(325.0, 100.0, 210.0, 220.0), Color(0.54, 0.18, 1.0, 1.0)),
        ("orange", Rect(570.0, 100.0, 210.0, 220.0), Color(1.0, 0.34, 0.06, 1.0)),
    )
    for key, bounds, fill in cards:
        root.add(
            SceneNode(
                key=key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                fill=fill,
            )
        )
    root.add(
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(130.0, 370.0, 650.0, 70.0),
            text="SwirUI native color-matrix post-processing",
            fill=Color(1.0, 1.0, 1.0, 1.0),
            font_size=30.0,
        )
    )
    return Scene(860.0, 520.0, root)


def main() -> None:
    renderer = WgpuRenderer(color_filter=ColorFilter.identity())
    app = App("SwirUI GPU Color Filters", renderer=renderer)
    window = Window(title="SwirUI — GPU Color Filters", width=860, height=520)
    window.set_scene(scene())
    app.add_window(window)
    app.start()

    started = time.monotonic()
    try:
        while window.is_open:
            elapsed = time.monotonic() - started
            hue = (elapsed * 32.0) % 360.0
            saturation = 0.85 + 0.35 * (0.5 + 0.5 * math.sin(elapsed * 1.4))
            renderer.set_color_filter(
                ColorFilter.hue_rotate(hue).then(ColorFilter.saturation(saturation))
            )
            app.invalidate(window)
            app.poll_events()
            app.render_pending()
            time.sleep(1.0 / 120.0)
    finally:
        app.stop()


if __name__ == "__main__":
    main()
