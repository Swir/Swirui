"""Show deterministic delay and finite repeat composition on one retained widget."""

from swirui import (
    AnimationController,
    AnimationSequence,
    App,
    Button,
    DelayAnimation,
    RepeatAnimation,
    Tween,
    Window,
    ease_in_out_cubic,
    ease_out_cubic,
    mount,
)
from swirui.rendering import Rect

app = App("SwirUI repeated animation")
window = app.add_window(Window(title="Delay + repeat animation", width=760, height=420))
button = Button(
    "REPEAT",
    key="repeat-target",
    bounds=Rect(250.0, 174.0, 260.0, 72.0),
    font_size=22.0,
)
mount(window, button)


def set_scale(value: float) -> None:
    button.set_visual_scale(value)


pulse = AnimationSequence(
    Tween(1.0, 1.12, 0.16, set_scale, easing=ease_out_cubic),
    Tween(1.12, 1.0, 0.24, set_scale, easing=ease_in_out_cubic),
)
AnimationController(app, window).play(
    DelayAnimation(0.35).then(RepeatAnimation(pulse, 4))
)
app.run()
