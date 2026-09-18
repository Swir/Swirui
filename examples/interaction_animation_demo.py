"""Hover, press and focus animation demo driven by the real window frame clock."""

from __future__ import annotations

from swirui import (
    AnimationController,
    App,
    Button,
    InteractionAnimationSpec,
    InteractionAnimator,
    Window,
    mount,
)
from swirui.rendering import Rect

app = App(name="SwirUI Interaction Animation")
window = app.add_window(Window(title="SwirUI interaction animation", width=520, height=260))
button = Button("Hover, press or focus me", bounds=Rect(140.0, 96.0, 240.0, 52.0))
mount(window, button)

controller = AnimationController(app, window)
animator = InteractionAnimator(
    controller,
    button,
    spec=InteractionAnimationSpec(
        hover_opacity=0.94,
        pressed_opacity=0.72,
        focus_opacity=0.88,
        duration=0.10,
        release_duration=0.18,
    ),
)

try:
    app.run()
finally:
    animator.dispose()
    controller.dispose()
