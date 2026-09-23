"""Micro-benchmark native PCM16 waveform envelope extraction through PyO3."""

from __future__ import annotations

import statistics
import time

import _swirui_native as native

BATCHES = 20
ITERATIONS = 100
CHANNELS = 2
FRAMES = 48_000 * 2
BUCKETS = 512
PCM16 = bytes(FRAMES * CHANNELS * 2)


def main() -> None:
    samples: list[float] = []
    for _ in range(BATCHES):
        started = time.perf_counter()
        for _ in range(ITERATIONS):
            envelope = native.waveform_envelope_pcm16(CHANNELS, PCM16, BUCKETS)
            if len(envelope) != BUCKETS:
                raise RuntimeError("Native waveform envelope returned an unexpected bucket count.")
        samples.append((time.perf_counter() - started) * 1000.0)

    print(
        "media_waveform_envelope "
        f"calls={BATCHES * ITERATIONS} "
        f"batch_median={statistics.median(samples):.3f}ms "
        f"batch_p95={statistics.quantiles(samples, n=20)[18]:.3f}ms "
        f"batch_max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
