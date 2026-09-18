"""Pointer-magnetic retained button demo driven by the real window frame clock."""

from __future__ import annotations

from swirui import (
    AnimationController,
    App,
    Button,
    MagneticInteraction,
    MagneticInteractionSpec,
    Window,
    mount,
)
from swirui.rendering import Rect

app = App(name="SwirUI Magnetic Interaction")
window = app.add_window(Window(title="SwirUI magnetic interaction", width=560, height=300))
button = Button("Move the pointer across me", bounds=Rect(150.0, 116.0, 260.0, 56.0))
mount(window, button)

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
