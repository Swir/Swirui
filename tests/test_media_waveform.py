from __future__ import annotations

import sys
import types

import pytest

from swirui.audio import AudioClip
from swirui.microphone import MicrophoneChunk
from swirui.rendering import Rect
from swirui.widgets.waveform import Waveform, WaveformEnvelope, waveform_envelope_pcm16


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

    def envelope(channels: int, payload: bytes, buckets: int) -> list[tuple[float, float]]:
        samples = [
            int.from_bytes(payload[offset : offset + 2], "little", signed=True)
            for offset in range(0, len(payload), 2)
        ]
        if not samples:
            return []
        frames = len(samples) // channels
        bucket_count = min(frames, buckets)
        result: list[tuple[float, float]] = []
        for bucket in range(bucket_count):
            start = bucket * frames // bucket_count
            end = max(start + 1, (bucket + 1) * frames // bucket_count)
            mixed: list[float] = []
            for frame in range(start, end):
                values = samples[frame * channels : (frame + 1) * channels]
                mixed.append(sum(value / 32768.0 for value in values) / channels)
            result.append((min(mixed), max(mixed)))
        return result

    return types.SimpleNamespace(
        validate_audio_pcm16=validate_audio,
        validate_microphone_pcm16=validate_audio,
        waveform_envelope_pcm16=envelope,
    )


def test_waveform_native_envelope_is_bounded_and_bucketed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    envelope = waveform_envelope_pcm16(
        pcm16(-32768, -16384, 0, 16384, 32767, 0),
        channels=1,
        buckets=3,
    )

    assert len(envelope) == 3
    assert envelope[0].minimum == pytest.approx(-1.0)
    assert envelope[0].maximum == pytest.approx(-0.5)
    assert envelope[1].minimum == pytest.approx(0.0)
    assert envelope[1].maximum == pytest.approx(0.5)
    assert envelope[2].maximum < 1.0


def test_waveform_accepts_audio_and_microphone_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    payload = pcm16(-32768, 0, 16384, 32767)
    audio = AudioClip(1_000, 1, payload)
    microphone = MicrophoneChunk(1_000, 1, payload)
    widget = Waveform(bounds=Rect(10.0, 20.0, 200.0, 80.0), buckets=4)

    widget.set_audio_clip(audio)
    first = widget.build_scene_node()
    assert len(widget.envelope) == 4
    assert widget.duration_ms == pytest.approx(4.0)
    assert widget.channels == 1
    assert first.clip_to_bounds is True
    assert len(first.children) == 5
    assert all(child.bounds.width >= 0.25 for child in first.children[1:])

    widget.set_microphone_chunk(microphone)
    assert widget.accessible_value_text == "4 waveform buckets, 4.0 ms, 1 channel"
    widget.clear()
    assert widget.envelope == ()
    assert widget.accessible_value_text == "No waveform data"


def test_waveform_handles_resize_without_reprocessing_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    widget = Waveform(bounds=Rect(0.0, 0.0, 120.0, 40.0), buckets=4)
    widget.set_envelope(
        [
            WaveformEnvelope(-1.0, 1.0),
            WaveformEnvelope(-0.5, 0.5),
            WaveformEnvelope(0.0, 0.0),
            WaveformEnvelope(-0.25, 0.75),
        ],
        duration_ms=20.0,
        channels=2,
    )
    before = widget.envelope
    widget.bounds = Rect(0.0, 0.0, 360.0, 120.0)
    scene = widget.build_scene_node()

    assert widget.envelope is before
    assert len(scene.children) == 5
    assert scene.children[1].bounds.height == pytest.approx(120.0)
    assert scene.children[2].bounds.height == pytest.approx(60.0)


def test_waveform_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="buckets"):
        Waveform(bounds=Rect(0.0, 0.0, 100.0, 40.0), buckets=0)
    with pytest.raises(ValueError, match="amplitudes"):
        WaveformEnvelope(-1.1, 0.2)
    with pytest.raises(ValueError, match="minimum"):
        WaveformEnvelope(0.7, 0.2)
