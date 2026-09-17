"""Rebuild a high-refresh scene while reusing cached retained glow geometry."""

from __future__ import annotations

import math
import time

from swirui import App, AppConfig, Window
from swirui.core import VisualQuality
from swirui.rendering import (
    Color,
    CornerRadius,
    EffectCache,
    Glow,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)


def build_scene(cache: EffectCache, phase: float) -> Scene:
    bounds = Rect(250.0, 150.0, 360.0, 180.0)
    radius = CornerRadius.uniform(34.0)
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 860.0, 520.0),
    )
    glow = Glow(
        color=Color(0.0, 0.62, 1.0, 0.52),
        blur_radius=42.0,
        spread=3.0,
    ).with_quality(VisualQuality.ULTRA)
    root.add(cache.render(glow, "cached-glow", bounds, corner_radius=radius, z_index=-1))
    pulse = 0.5 + 0.5 * math.sin(phase)
    root.add(
        SceneNode(
            key="card",
            kind=SceneNodeKind.RECTANGLE,
            bounds=bounds,
            fill=Color(0.04 + 0.04 * pulse, 0.09, 0.16 + 0.08 * pulse, 1.0),
            corner_radius=radius,
        )
    )
    root.add(
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(300.0, 215.0, 270.0, 54.0),
            text="SwirUI Effect Cache",
            fill=Color(0.88, 0.96, 1.0, 1.0),
            font_size=30.0,
            z_index=1,
        )
    )
    return Scene(860.0, 520.0, root)


def main() -> None:
    cache = EffectCache(max_entries=32)
    app = App(
        "SwirUI Effect Cache",
        config=AppConfig(target_fps=120, visual_quality=VisualQuality.ULTRA),
    )
    window = Window(title="SwirUI — Retained Effect Cache", width=860, height=520)
    window.set_scene(build_scene(cache, 0.0))
    app.add_window(window)
    app.start()

    started = time.monotonic()
    try:
        while window.is_open:
            elapsed = time.monotonic() - started
            window.set_scene(build_scene(cache, elapsed * 2.0))
            app.poll_events()
            app.render_pending()
            time.sleep(1.0 / 120.0)
    finally:
        stats = cache.stats
        print(
            "effect-cache",
            f"entries={stats.entries}",
            f"hits={stats.hits}",
            f"misses={stats.misses}",
            f"hit_rate={stats.hit_rate:.1%}",
        )
        app.stop()


if __name__ == "__main__":
    main()
