"""Frame-rate-independent opacity and geometry animation demo for SwirUI."""

from __future__ import annotations

import time

from swirui import AnimationController, Button, animate_bounds, animate_opacity, linear
from swirui.rendering import Rect

button = Button("SwirUI", bounds=Rect(20.0, 40.0, 180.0, 52.0))
controller = AnimationController()

sequence = animate_opacity(button, 0.35, duration=0.6, easing=linear).then(
    animate_bounds(
        button,
        Rect(320.0, 160.0, 240.0, 64.0),
        duration=1.2,
        easing=linear,
    ),
    animate_opacity(button, 1.0, duration=0.5, easing=linear),
)

started = time.monotonic()
handle = controller.play(sequence, start_time=started)
while handle.running:
    controller.tick(time.monotonic())
    time.sleep(1.0 / 120.0)

print("final bounds:", button.bounds)
print("final opacity:", button.opacity)
