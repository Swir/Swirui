from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native spectrum gate")


def test_windows_native_spectrum_is_compiled_bounded_and_deterministic() -> None:
    import _swirui_native as native

    samples = [32767 if index % 2 == 0 else -32768 for index in range(64)]
    payload = b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)
    spectrum = native.spectrum_magnitudes_pcm16(1, payload, 33)

    assert len(spectrum) == 33
    assert spectrum[0] < 0.05
    assert spectrum[-1] > 0.95
    assert all(0.0 <= value <= 1.0 for value in spectrum)
