"""Play a short generated PCM16 tone through the native Windows AudioPlayer."""

from __future__ import annotations

import math
import time

from swirui.audio import AudioPlayer, audio_clip_from_pcm16

SAMPLE_RATE = 48_000
FREQUENCY_HZ = 440.0
DURATION_SECONDS = 1.0


def sine_pcm16() -> bytes:
    samples = bytearray()
    frame_count = int(SAMPLE_RATE * DURATION_SECONDS)
    for frame in range(frame_count):
        phase = 2.0 * math.pi * FREQUENCY_HZ * frame / SAMPLE_RATE
        sample = int(math.sin(phase) * 12_000)
        samples.extend(sample.to_bytes(2, "little", signed=True))
    return bytes(samples)


def main() -> None:
    clip = audio_clip_from_pcm16(SAMPLE_RATE, 1, sine_pcm16())
    player = AudioPlayer(
        clip,
        autoplay=True,
        volume=0.25,
        accessible_name="Generated 440 Hz tone",
    )
    time.sleep(0.35)
    player.pause().seek(0.5 * clip.duration_ms)
    player.play()
    time.sleep(0.35)
    player.stop()


if __name__ == "__main__":
    main()
