from __future__ import annotations

import sys
import types

import pytest

from swirui.audio import AudioClip
from swirui.microphone import MicrophoneChunk
from swirui.rendering import Rect
from swirui.widgets.spectrum import SpectrumVisualizer, spectrum_magnitudes_pcm16


def pcm16(*samples: int) -> bytes:
    return b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in samples)


def fake_native() -> types.SimpleNamespace:
    def validate_audio(
        sample_rate: int,
        channels: int,
        payload: bytes,
    ) -> tuple[int, int, int, float]:
        if sample_rate <= 0 or channels <= 0 or len(payload) % (channels * 2):
            raise ValueError("invalid PCM16")
        frames = len(payload) // channels // 2
        return sample_rate, channels, frames, frames / sample_rate * 1000.0

    def spectrum(channels: int, payload: bytes, bins: int) -> list[float]:
        samples = [
            int.from_bytes(payload[offset : offset + 2], "little", signed=True)
            for offset in range(0, len(payload), 2)
        ]
        if not samples:
            return []
        frames = len(samples) // channels
        mixed = [
            sum(samples[frame * channels : (frame + 1) * channels]) / channels / 32768.0
            for frame in range(frames)
        ]
        peak = min(1.0, max(abs(value) for value in mixed))
        return [peak * (index + 1) / bins for index in range(min(bins, frames // 2 + 1))]

    return types.SimpleNamespace(
        validate_audio_pcm16=validate_audio,
        validate_microphone_pcm16=validate_audio,
        spectrum_magnitudes_pcm16=spectrum,
    )


def test_spectrum_native_analysis_is_bounded_and_bucketed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    magnitudes = spectrum_magnitudes_pcm16(
        pcm16(-32768, -16384, 0, 16384, 32767, 0),
        channels=1,
        bins=3,
    )

    assert len(magnitudes) == 3
    assert magnitudes[0] == pytest.approx(1.0 / 3.0)
    assert magnitudes[1] == pytest.approx(2.0 / 3.0)
    assert magnitudes[2] == pytest.approx(1.0)
    assert all(0.0 <= value <= 1.0 for value in magnitudes)


def test_spectrum_accepts_audio_and_microphone_sources_with_smoothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    loud = pcm16(-32768, 0, 16384, 32767)
    quiet = pcm16(-8192, 0, 4096, 8192)
    audio = AudioClip(8_000, 1, loud)
    microphone = MicrophoneChunk(8_000, 1, quiet)
    widget = SpectrumVisualizer(
        bounds=Rect(10.0, 20.0, 200.0, 80.0),
        bins=3,
        smoothing=0.5,
    )

    widget.set_audio_clip(audio)
    first = widget.magnitudes
    scene = widget.build_scene_node()
    assert len(first) == 3
    assert widget.sample_rate == 8_000
    assert widget.channels == 1
    assert scene.clip_to_bounds is True
    assert len(scene.children) == 3
    assert all(child.bounds.width >= 0.25 for child in scene.children)

    widget.set_microphone_chunk(microphone)
    assert widget.magnitudes[2] < first[2]
    assert widget.magnitudes[2] > 0.25
    assert "spectrum bins" in widget.accessible_value_text
    assert "Hz" in widget.accessible_value_text
    widget.reset()
    assert widget.magnitudes == ()
    assert widget.accessible_value_text == "No spectrum data"


def test_spectrum_handles_resize_without_reprocessing_source() -> None:
    widget = SpectrumVisualizer(bounds=Rect(0.0, 0.0, 120.0, 40.0), bins=4)
    widget.set_magnitudes(
        [1.0, 0.5, 0.25, 0.0],
        sample_rate=48_000,
        channels=2,
    )
    before = widget.magnitudes
    widget.bounds = Rect(0.0, 0.0, 360.0, 120.0)
    scene = widget.build_scene_node()

    assert widget.magnitudes is before
    assert len(scene.children) == 4
    assert scene.children[0].bounds.height == pytest.approx(120.0)
    assert scene.children[1].bounds.height == pytest.approx(60.0)
    assert scene.children[2].bounds.height == pytest.approx(30.0)


def test_spectrum_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="bins"):
        SpectrumVisualizer(bounds=Rect(0.0, 0.0, 100.0, 40.0), bins=0)
    with pytest.raises(ValueError, match="smoothing"):
        SpectrumVisualizer(bounds=Rect(0.0, 0.0, 100.0, 40.0), smoothing=1.0)
    widget = SpectrumVisualizer(bounds=Rect(0.0, 0.0, 100.0, 40.0))
    with pytest.raises(ValueError, match="magnitudes"):
        widget.set_magnitudes([1.1])
