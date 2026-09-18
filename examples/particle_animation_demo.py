"""Deterministic GPU-batched particle animation example."""

from __future__ import annotations

from swirui import AnimationStatus, ParticleField
from swirui.rendering import Color, Rect

field = ParticleField(
    bounds=Rect(0.0, 0.0, 720.0, 420.0),
    particle_count=96,
    seed=2026,
    colors=(
        Color.from_hex("#0088FF"),
        Color.from_hex("#62E5FF"),
        Color.from_hex("#F4FAFF"),
    ),
    speed_range=(24.0, 90.0),
    size_range=(2.0, 7.0),
    gravity_y=22.0,
    loop=False,
    duration=2.0,
).start()

frame_pattern = (1.0 / 60.0, 1.0 / 144.0, 1.0 / 120.0, 1.0 / 75.0)
frame = 0
while field.status is AnimationStatus.RUNNING:
    field.advance(frame_pattern[frame % len(frame_pattern)])
    frame += 1

print(f"particles={field.particle_count} elapsed={field.elapsed:.3f}s frames={frame}")
print("final visible samples:", len(field.samples()))
