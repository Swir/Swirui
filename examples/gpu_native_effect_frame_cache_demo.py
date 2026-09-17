"""Present an unchanged frosted-glass scene from the retained native GPU frame cache."""

from __future__ import annotations

import time

from swirui import App, AppConfig, Window
from swirui.rendering import (
    Color,
    CornerRadius,
    FrostedGlass,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def build_scene() -> Scene:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, 900.0, 540.0))
    root.add(
        SceneNode(
            "background",
            SceneNodeKind.RECTANGLE,
            Rect(0.0, 0.0, 900.0, 540.0),
            fill=Color.from_hex("#071225"),
        ),
        SceneNode(
            "accent",
            SceneNodeKind.RECTANGLE,
            Rect(125.0, 115.0, 310.0, 310.0),
            fill=Color.from_hex("#007DFF"),
            corner_radius=CornerRadius.uniform(72.0),
            z_index=1,
        ),
    )
    glass = FrostedGlass(
        blur_radius=30.0,
        tint=Color(0.12, 0.22, 0.36, 0.52),
        corner_radius=CornerRadius.uniform(34.0),
    ).to_scene_node("glass", Rect(245.0, 145.0, 485.0, 250.0), z_index=2)
    glass.add(
        SceneNode(
            "title",
            SceneNodeKind.TEXT,
            Rect(305.0, 235.0, 370.0, 58.0),
            text="Native effect-frame cache",
            fill=Color.from_hex("#FFFFFF"),
            font_size=30.0,
            z_index=10,
        )
    )
    root.add(glass)
    return Scene(900.0, 540.0, root)


def main() -> None:
    renderer = WgpuRenderer()
    app = App(
        "SwirUI Native Effect Cache",
        config=AppConfig(target_fps=120),
        renderer=renderer,
    )
    window = Window(title="SwirUI — Native Effect Frame Cache", width=900, height=540)
    window.set_scene(build_scene())
    app.add_window(window)
    app.start()

    started = time.monotonic()
    next_report = started + 1.0
    try:
        while window.is_open:
            app.poll_events()
            app.invalidate(window)
            app.render_pending()
            now = time.monotonic()
            if now >= next_report:
                print(
                    "native-effect-cache",
                    f"hits={renderer.native_effect_cache_hits}",
                    f"misses={renderer.native_effect_cache_misses}",
                    f"prepared_hits={renderer.backdrop_payload_cache_hits}",
                )
                next_report = now + 1.0
            time.sleep(1.0 / 120.0)
    finally:
        app.stop()


if __name__ == "__main__":
    main()
