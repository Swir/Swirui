"""Frame-rate-independent animation timing and chaining example."""

from __future__ import annotations

from swirui import AnimationStatus, State, Tween, ease_in_out_cubic, tween_state

position = State(0.0)
position.subscribe(lambda value: print(f"position={value:6.2f}"))

move_out = tween_state(position, 320.0, 0.6, easing=ease_in_out_cubic)
move_back = Tween(320.0, 0.0, 0.4, position.set, easing=ease_in_out_cubic)
sequence = move_out.then(move_back).start()

# Real applications can hand the same sequence to AnimationController, which
# advances it from App.frame_rendered telemetry. This deterministic loop makes
# the example runnable on every platform without opening a native window.
frame_delta = 1.0 / 144.0
while sequence.status is AnimationStatus.RUNNING:
    sequence.advance(frame_delta)

print(f"completed={sequence.status.value} final={position.value:.2f}")
