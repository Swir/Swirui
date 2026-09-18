"""Show composable fade, slide and uniform visual-scale animation."""

from swirui import (
    AnimationController,
    AnimationParallel,
    App,
    Button,
    FadeTransition,
    ScaleTransition,
    SlideTransition,
    Window,
    linear,
    mount,
)
from swirui.rendering import Point, Rect

app = App("SwirUI transform animation")
window = app.add_window(Window(title="Retained transform animation", width=720, height=420))
button = Button("GPU retained transform", bounds=Rect(220.0, 165.0, 280.0, 72.0))
mount(window, button)

controller = AnimationController(app, window)
controller.play(
    AnimationParallel(
        FadeTransition(button, 0.7, duration=0.8, easing=linear),
        SlideTransition(button, Point(60.0, -24.0), duration=0.8, easing=linear),
        ScaleTransition(button, 0.72, duration=0.8, easing=linear),
    )
)

app.run()
