"""Show retained reveal, center-flip and matching-aspect morph transitions."""

from swirui import (
    AnimationController,
    AnimationSequence,
    App,
    Button,
    Component,
    FlipTransition,
    MorphTransition,
    RevealTransition,
    Window,
    linear,
    mount,
)
from swirui.rendering import Rect

app = App("SwirUI advanced transform animation")
window = app.add_window(Window(title="Morph / flip / reveal", width=860, height=480))

root = Component("advanced-transform-demo")
source = Button(
    "Front",
    key="morph-source",
    bounds=Rect(110.0, 185.0, 180.0, 72.0),
    font_size=22.0,
)
target = Button(
    "Target",
    key="morph-target",
    bounds=Rect(530.0, 149.0, 270.0, 108.0),
    font_size=22.0,
)
root.add(source, target)
mount(window, root)


def swap_face() -> None:
    source.text = "Back"


controller = AnimationController(app, window)
controller.play(
    AnimationSequence(
        RevealTransition(source, from_scale=0.84, duration=0.55, easing=linear),
        FlipTransition(source, duration=0.65, easing=linear, on_midpoint=swap_face),
        MorphTransition(source, target, duration=0.90, easing=linear),
    )
)

app.run()
