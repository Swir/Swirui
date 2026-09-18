"""Demonstrate pointer-driven magnetic motion on a retained SwirUI button."""

from __future__ import annotations

from swirui import (
    AnimationController,
    App,
    Button,
    MagneticInteractionAnimator,
    MagneticInteractionSpec,
    Window,
    mount,
)
from swirui.rendering import Rect

app = App(name="SwirUI Magnetic Interaction Demo")
window = app.add_window(
    Window(title="SwirUI magnetic interaction", width=720, height=420)
)
button = Button(
    "Move near me",
    key="magnetic-button",
    bounds=Rect(240.0, 176.0, 240.0, 64.0),
)
runtime = mount(window, button)
controller = AnimationController(app, window)
magnetic = MagneticInteractionAnimator(
    controller,
    button,
    spec=MagneticInteractionSpec(strength=0.24, max_offset=20.0),
)

try:
    app.run()
finally:
    magnetic.dispose()
    controller.dispose()
    runtime.unmount()
