"""Animate retained widget transforms with deterministic scalar keyframes."""

from swirui import (
    AnimationController,
    AnimationParallel,
    App,
    Button,
    Component,
    Keyframe,
    KeyframeAnimation,
    Window,
    ease_in_out_cubic,
    ease_out_bounce,
    mount,
)
from swirui.rendering import Rect

app = App("SwirUI keyframe animation")
window = app.add_window(Window(title="Deterministic keyframes", width=900, height=500))
root = Component("keyframe-demo")
button = Button(
    "KEYFRAMES",
    key="keyframe-target",
    bounds=Rect(100.0, 210.0, 190.0, 68.0),
    font_size=20.0,
)
root.add(button)
mount(window, root)


def set_x(value: float) -> None:
    button.set_visual_offset(value, 0.0)


def set_scale(value: float) -> None:
    button.set_visual_scale(value)


motion = KeyframeAnimation(
    (
        Keyframe(0.0, 0.0, ease_in_out_cubic),
        Keyframe(0.35, 420.0, ease_out_bounce),
        Keyframe(0.72, 300.0, ease_in_out_cubic),
        Keyframe(1.0, 500.0),
    ),
    2.4,
    set_x,
)
pulse = KeyframeAnimation(
    (
        Keyframe(0.0, 1.0, ease_in_out_cubic),
        Keyframe(0.35, 1.14, ease_in_out_cubic),
        Keyframe(0.72, 0.96, ease_in_out_cubic),
        Keyframe(1.0, 1.0),
    ),
    2.4,
    set_scale,
)
AnimationController(app, window).play(AnimationParallel(motion, pulse))
app.run()
