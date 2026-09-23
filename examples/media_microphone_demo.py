"""Minimal native microphone-input example for SwirUI."""

from __future__ import annotations

import time

from swirui.microphone import MicrophoneInput, microphone_devices


def main() -> None:
    devices = microphone_devices()
    if not devices:
        print("No native microphone input device is available.")
        return

    device = next((candidate for candidate in devices if candidate.is_default), devices[0])
    print(f"capturing from {device.name}")
    with MicrophoneInput(device.index, buffer_ms=1_000) as microphone:
        time.sleep(0.25)
        chunk = microphone.read()
        if chunk is None:
            print("No microphone frames arrived during the sample window.")
            return
        print(
            f"captured {chunk.frame_count} frames at {chunk.sample_rate} Hz / "
            f"{chunk.channels} channel(s); dropped={microphone.dropped_frames}"
        )


if __name__ == "__main__":
    main()
