"""SpectrumVisualizer demo using a synthetic PCM16 tone."""

from __future__ import annotations

import math

from swirui import SpectrumVisualizer
from swirui.audio import AudioClip
from swirui.rendering import Rect

SAMPLE_RATE = 48_000
FRAMES = 4_096


def _tone() -> bytes:
    samples = [
        int(
            (
                0.72 * math.sin(2.0 * math.pi * 440.0 * frame / SAMPLE_RATE)
                + 0.22 * math.sin(2.0 * math.pi * 1_760.0 * frame / SAMPLE_RATE)
            )
            * 24_000
        )
        for frame in range(FRAMES)
    ]
    return b"".join(
        max(-32768, min(32767, sample)).to_bytes(2, "little", signed=True)
        for sample in samples
    )


def main() -> None:
    clip = AudioClip(SAMPLE_RATE, 1, _tone())
    spectrum = SpectrumVisualizer(bounds=Rect(24.0, 24.0, 720.0, 240.0), bins=96)
    spectrum.set_audio_clip(clip)
    scene = spectrum.build_scene_node()

    print(
        f"SpectrumVisualizer: bins={len(spectrum.magnitudes)}, "
        f"scene_bars={len(scene.children)}, "
        f"peak={max(spectrum.magnitudes, default=0.0):.3f}"
    )
    print(spectrum.accessible_value_text)


if __name__ == "__main__":
    main()
