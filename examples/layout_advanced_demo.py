"""Dock, flow, overlay and constraint layout demo for SwirUI 0.5."""

from swirui import (
    App,
    Button,
    ConstraintLayout,
    ConstraintSpec,
    Dock,
    DockPanel,
    Flow,
    Insets,
    Overlay,
    OverlayPlacement,
    Window,
    mount,
)
from swirui.rendering import Rect


def main() -> int:
    app = App("SwirUI advanced layouts")
    window = app.add_window(
        Window(title="SwirUI — Dock + Flow + Overlay + Constraints", width=1100, height=700)
    )

    nav = Flow(
        bounds=Rect(0.0, 0.0, 220.0, 1.0),
        padding=Insets.all(14.0),
        spacing=10.0,
        line_spacing=10.0,
    )
    for label in ("Home", "Projects", "Inspector", "Performance"):
        nav.add(Button(label, bounds=Rect(0.0, 0.0, 180.0, 44.0)))

    action = Button("Build app", bounds=Rect(0.0, 0.0, 160.0, 48.0))
    workspace = ConstraintLayout(bounds=Rect(0.0, 0.0, 1.0, 1.0), padding=24.0)
    workspace.add(action)
    workspace.set_constraints(
        action,
        ConstraintSpec(right=20.0, bottom=20.0, width=180.0, height=52.0),
    )

    overlay = Overlay(bounds=Rect(0.0, 0.0, 1.0, 1.0))
    overlay.add(workspace)
    overlay.set_placement(
        workspace,
        OverlayPlacement(),
    )

    root = DockPanel(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=20.0,
        spacing=18.0,
    )
    root.add(nav, overlay)
    root.set_dock(nav, Dock.LEFT)
    mount(window, root)

    app.start()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
