"""Micro-benchmark for the native Spectrum PCM16 analysis kernel."""

from __future__ import annotations

import math
import statistics
import time

import _swirui_native as native

SAMPLE_RATE = 48_000
FRAMES = 4_096
BINS = 128
ITERATIONS = 80
BUDGET_MS = 20.0


def _pcm16_sine() -> bytes:
    samples = [
        int(math.sin(2.0 * math.pi * 1_000.0 * frame / SAMPLE_RATE) * 28_000)
        for frame in range(FRAMES)
    ]
    return b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)


def main() -> None:
    payload = _pcm16_sine()
    timings_ms: list[float] = []
    for _ in range(ITERATIONS):
        started = time.perf_counter()
        spectrum = native.spectrum_magnitudes_pcm16(1, payload, BINS)
        timings_ms.append((time.perf_counter() - started) * 1_000.0)
        if len(spectrum) != BINS:
            raise RuntimeError("Native spectrum returned an unexpected bin count.")

    median_ms = statistics.median(timings_ms)
    p95_ms = sorted(timings_ms)[int((len(timings_ms) - 1) * 0.95)]
    print(
        f"spectrum_pcm16 frames={FRAMES} bins={BINS} "
        f"median_ms={median_ms:.3f} p95_ms={p95_ms:.3f} budget_ms={BUDGET_MS:.1f}"
    )
    if p95_ms > BUDGET_MS:
        raise SystemExit(
            f"Spectrum p95 {p95_ms:.3f} ms exceeded {BUDGET_MS:.1f} ms budget."
        )


if __name__ == "__main__":
    main()
