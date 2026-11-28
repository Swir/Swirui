"""Pointer-magnetic retained button demo driven by the real window frame clock."""

from __future__ import annotations

from dataclasses import replace

from swirui import (
    FUTURE_DARK,
    AnimationController,
    App,
    Button,
    Label,
    MagneticInteraction,
    MagneticInteractionSpec,
    Panel,
    SilkRibbon,
    SurfaceStyle,
    ThemeSurface,
    Window,
    mount,
)
from swirui.rendering import Rect

app = App(name="SwirUI Magnetic Interaction")
window = app.add_window(Window(title="SwirUI magnetic interaction", width=620, height=300,
                               min_width=620, min_height=300))
iris = replace(FUTURE_DARK.with_accent("#BA8DFF"), control_radius=18)
mint = iris.with_accent("#64D9B4")
root = Panel(bounds=Rect(0, 0, 620, 300), theme=iris)
card = ThemeSurface(bounds=Rect(284, 49, 302, 202),
                    style=SurfaceStyle(kind="glass", tint_opacity=.70, elevation=8))
button = Button("Use mint", key="change-accent", bounds=Rect(348, 124, 174, 52),
                text_align="center", font_size=18)
card.add(button)
root.add(
    SilkRibbon(bounds=Rect(247, 9, 375, 255)),
    Label("Magnetic hover", bounds=Rect(32, 80, 248, 48), font_size=30),
    Label("Move along the button’s edges\nto draw it toward you.",
          bounds=Rect(34, 140, 236, 60), font_size=16),
    card,
)
mount(window, root)


def change_accent(*_args: object) -> None:
    root.theme = mint if root.theme is iris else iris
    button.text = "Use iris" if root.theme is mint else "Use mint"


button.on("click", change_accent)

controller = AnimationController(app, window)
magnetic = MagneticInteraction(
    controller,
    button,
    spec=MagneticInteractionSpec(
        max_offset=14.0,
        stiffness=240.0,
        damping=22.0,
    ),
)

try:
    app.run()
finally:
    magnetic.dispose()
    controller.dispose()
