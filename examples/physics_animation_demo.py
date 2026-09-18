"""Frame-rate-independent spring, inertial decay and parallel animation demo."""

from __future__ import annotations

from swirui import (
    AnimationParallel,
    AnimationStatus,
    DecayAnimation,
    SpringAnimation,
    State,
    Tween,
    ease_in_out_cubic,
)

position = State(0.0)
opacity = State(0.0)
fling = State(0.0)

intro = AnimationParallel(
    SpringAnimation(
        0.0,
        320.0,
        position.set,
        stiffness=180.0,
        damping=22.0,
    ),
    Tween(0.0, 1.0, 0.35, opacity.set, easing=ease_in_out_cubic),
)
intro.start()

# Sampling uses elapsed time, so an irregular frame pattern remains deterministic.
frame_pattern = (1.0 / 60.0, 1.0 / 144.0, 1.0 / 120.0, 1.0 / 75.0)
frame = 0
while intro.status is AnimationStatus.RUNNING:
    intro.advance(frame_pattern[frame % len(frame_pattern)])
    frame += 1

momentum = DecayAnimation(
    0.0,
    780.0,
    fling.set,
    friction=7.0,
    velocity_threshold=4.0,
).start()
while momentum.status is AnimationStatus.RUNNING:
    momentum.advance(frame_pattern[frame % len(frame_pattern)])
    frame += 1

print(f"spring position={position.value:.2f} opacity={opacity.value:.2f}")
print(f"decay displacement={fling.value:.2f} frames={frame}")
