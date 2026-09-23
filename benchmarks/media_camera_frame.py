"""Micro-benchmark native camera-frame validation through the PyO3 bridge."""

from __future__ import annotations

import statistics
import time

import _swirui_native as native

BATCHES = 20
ITERATIONS = 5_000
WIDTH = 64
HEIGHT = 36
FRAME = bytes((20, 40, 80, 255)) * (WIDTH * HEIGHT)


def main() -> None:
    samples: list[float] = []
    for _ in range(BATCHES):
        started = time.perf_counter()
        for _ in range(ITERATIONS):
            native.validate_camera_rgba_frame(WIDTH, HEIGHT, FRAME)
        samples.append((time.perf_counter() - started) * 1000.0)

    print(
        "media_camera_frame_validation "
        f"calls={BATCHES * ITERATIONS} "
        f"batch_median={statistics.median(samples):.3f}ms "
        f"batch_p95={statistics.quantiles(samples, n=20)[18]:.3f}ms "
        f"batch_max={max(samples):.3f}ms"
    )


if __name__ == "__main__":
    main()
