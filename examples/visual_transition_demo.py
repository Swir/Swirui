"""Run retained fade and slide transitions on SwirUI's window-scoped frame clock."""

from __future__ import annotations

from swirui import (
    AnimationController,
    AnimationParallel,
    App,
    Card,
    Component,
    FadeTransition,
    Label,
    SlideTransition,
    Window,
    mount,
)
from swirui.rendering import Color, Point, Rect


def main() -> int:
    app = App("SwirUI Visual Transition")
    window = app.add_window(
        Window(title="SwirUI — Fade + Slide Transition", width=820, height=460)
    )
    root = Component("visual transition demo")
    card = Card(key="transition-card", bounds=Rect(250.0, 132.0, 320.0, 176.0))
    card.add(
        Label(
            "Fade + Slide",
            bounds=Rect(315.0, 196.0, 210.0, 48.0),
            font_size=27.0,
            color=Color.from_hex("#62E5FF"),
        )
    )
    root.add(card)
    mount(window, root)

    controller = AnimationController(app, window)
    controller.play(
        AnimationParallel(
            FadeTransition(card, from_opacity=0.0, duration=0.65),
            SlideTransition(
                card,
                from_offset=Point(96.0, 0.0),
                duration=0.65,
            ),
        )
    )

    try:
        return app.run()
    finally:
        controller.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
