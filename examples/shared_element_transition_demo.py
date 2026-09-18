"""Move one retained visual identity between two layouts on the SwirUI frame clock."""

from __future__ import annotations

from swirui import (
    AnimationController,
    App,
    Card,
    Component,
    Label,
    SharedElementTransition,
    Window,
    mount,
)
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI Shared Element Transition")
    window = app.add_window(
        Window(title="SwirUI — Shared Element Transition", width=820, height=460)
    )
    root = Component("shared element demo")

    source = Card(key="album-card-source", bounds=Rect(92.0, 146.0, 188.0, 132.0))
    source.add(
        Label(
            "SWIR",
            bounds=Rect(130.0, 184.0, 112.0, 42.0),
            font_size=28.0,
            color=Color.from_hex("#62E5FF"),
        )
    )

    target = Card(key="album-card-target", bounds=Rect(470.0, 92.0, 256.0, 216.0))
    target.add(
        Label(
            "SWIR",
            bounds=Rect(542.0, 164.0, 112.0, 42.0),
            font_size=28.0,
            color=Color.from_hex("#62E5FF"),
        )
    )

    root.add(source, target)
    mount(window, root)

    controller = AnimationController(app, window)
    controller.play(SharedElementTransition(source, target, duration=0.85))

    try:
        return app.run()
    finally:
        controller.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
