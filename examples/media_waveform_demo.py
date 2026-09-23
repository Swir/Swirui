"""Build a retained SwirUI waveform scene from a short synthetic PCM16 clip."""

from __future__ import annotations

import math

from swirui.audio import AudioClip
from swirui.rendering import Rect
from swirui.widgets.waveform import Waveform

SAMPLE_RATE = 48_000
DURATION_SECONDS = 0.25


def sine_pcm16() -> bytes:
    frames = int(SAMPLE_RATE * DURATION_SECONDS)
    samples = (
        int(math.sin(2.0 * math.pi * 220.0 * frame / SAMPLE_RATE) * 24_000)
        for frame in range(frames)
    )
    return b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)


def main() -> None:
    clip = AudioClip(SAMPLE_RATE, 1, sine_pcm16())
    waveform = Waveform(bounds=Rect(24.0, 24.0, 720.0, 220.0), buckets=256)
    waveform.set_audio_clip(clip)
    scene = waveform.build_scene_node()
    print(
        f"Waveform ready: buckets={len(waveform.envelope)} "
        f"duration={waveform.duration_ms:.1f}ms retained_nodes={len(scene.children) + 1}"
    )


if __name__ == "__main__":
    main()
