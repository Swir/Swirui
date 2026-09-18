"""Cross-fade and slide two retained pages on the real SwirUI frame clock."""

from __future__ import annotations

from swirui import (
    AnimationController,
    App,
    Card,
    Component,
    Label,
    PageTransition,
    PageTransitionDirection,
    Window,
    mount,
)
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI Page Transition")
    window = app.add_window(Window(title="SwirUI — Page Transition", width=760, height=460))
    root = Component("page transition demo")

    outgoing = Card(key="page-outgoing", bounds=Rect(130.0, 92.0, 500.0, 276.0))
    outgoing.add(
        Label(
            "Dashboard",
            bounds=Rect(178.0, 142.0, 260.0, 44.0),
            font_size=30.0,
            color=Color.from_hex("#F4FAFF"),
        ),
        Label(
            "Outgoing retained page",
            bounds=Rect(178.0, 204.0, 280.0, 30.0),
            color=Color.from_hex("#8DA8B8"),
        ),
    )

    incoming = Card(key="page-incoming", bounds=Rect(130.0, 92.0, 500.0, 276.0))
    incoming.add(
        Label(
            "Inspector",
            bounds=Rect(178.0, 142.0, 260.0, 44.0),
            font_size=30.0,
            color=Color.from_hex("#62E5FF"),
        ),
        Label(
            "Incoming retained page",
            bounds=Rect(178.0, 204.0, 280.0, 30.0),
            color=Color.from_hex("#8DA8B8"),
        ),
    )

    root.add(outgoing, incoming)
    mount(window, root)

    controller = AnimationController(app, window)
    controller.play(
        PageTransition(
            outgoing,
            incoming,
            duration=0.7,
            distance=72.0,
            direction=PageTransitionDirection.LEFT,
        )
    )

    try:
        return app.run()
    finally:
        controller.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
