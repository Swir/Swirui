from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native waveform gate")


def test_windows_native_waveform_envelope_is_compiled_and_deterministic() -> None:
    import _swirui_native as native

    payload = b"".join(
        sample.to_bytes(2, "little", signed=True)
        for sample in (-32768, -16384, 0, 16384, 32767, 0)
    )
    envelope = native.waveform_envelope_pcm16(1, payload, 3)

    assert len(envelope) == 3
    assert envelope[0][0] == pytest.approx(-1.0)
    assert envelope[0][1] == pytest.approx(-0.5)
    assert envelope[1][0] == pytest.approx(0.0)
    assert envelope[1][1] == pytest.approx(0.500015, rel=1e-4)
    assert envelope[2][1] == pytest.approx(1.0)
