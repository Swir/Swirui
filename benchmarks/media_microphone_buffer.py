"""Micro-benchmark native microphone PCM16 validation through the PyO3 bridge."""

from __future__ import annotations

import statistics
import time

import _swirui_native as native

BATCHES = 20
ITERATIONS = 5_000
SAMPLE_RATE = 48_000
CHANNELS = 2
FRAMES = 128
PCM16 = bytes(FRAMES * CHANNELS * 2)


def main() -> None:
    samples: list[float] = []
    for _ in range(BATCHES):
        started = time.perf_counter()
        for _ in range(ITERATIONS):
            native.validate_microphone_pcm16(SAMPLE_RATE, CHANNELS, PCM16)
        samples.append((time.perf_counter() - started) * 1000.0)

    print(
        "media_microphone_pcm_validation "
        f"calls={BATCHES * ITERATIONS} "
        f"batch_median={statistics.median(samples):.3f}ms "
        f"batch_p95={statistics.quantiles(samples, n=20)[18]:.3f}ms "
        f"batch_max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
