"""Micro-benchmark native AudioPlayer timeline selection through the PyO3 bridge."""

from __future__ import annotations

import statistics
import time

import _swirui_native as native

BATCHES = 20
ITERATIONS = 10_000
SAMPLE_RATE = 48_000
FRAME_COUNT = SAMPLE_RATE * 60


def main() -> None:
    samples: list[float] = []
    for batch in range(BATCHES):
        started = time.perf_counter()
        for index in range(ITERATIONS):
            elapsed_ms = (batch * ITERATIONS + index) / 8.0
            native.audio_frame_index(
                elapsed_ms,
                SAMPLE_RATE,
                FRAME_COUNT,
                True,
            )
        samples.append((time.perf_counter() - started) * 1000.0)

    print(
        "media_audio_timeline "
        f"calls={BATCHES * ITERATIONS} "
        f"batch_median={statistics.median(samples):.3f}ms "
        f"batch_p95={statistics.quantiles(samples, n=20)[18]:.3f}ms "
        f"batch_max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
