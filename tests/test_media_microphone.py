from __future__ import annotations

import sys
import types

import pytest

from swirui.microphone import (
    MicrophoneChunk,
    MicrophoneDevice,
    MicrophoneInput,
    microphone_devices,
    native_microphone_input_supported,
)


class RecordingCapture:
    def __init__(self) -> None:
        self.sample_rate = 1_000
        self.channels = 1
        self.device_name = "Test microphone"
        self.is_open = True
        self.is_active = True
        self._chunks = [pcm16_mono(10, -10, 20, -20)]
        self._dropped_frames = 3
        self._last_error: str | None = None
        self.clear_calls = 0

    def read_pcm16(self, max_frames: int | None = None) -> bytes:
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if max_frames is None:
            return chunk
        return chunk[: max_frames * self.channels * 2]

    def available_frames(self) -> int:
        if not self._chunks:
            return 0
        return len(self._chunks[0]) // 2 // self.channels

    def dropped_frames(self) -> int:
        return self._dropped_frames

    def clear(self) -> None:
        self._chunks.clear()
        self.clear_calls += 1

    def pause(self) -> None:
        self.is_active = False

    def resume(self) -> None:
        self.is_active = True

    def close(self) -> None:
        self.is_open = False
        self.is_active = False

    def last_error(self) -> str | None:
        return self._last_error


class FakeNativeCapture(RecordingCapture):
    def __init__(self, index: int | None, buffer_ms: int) -> None:
        super().__init__()
        self.index = index
        self.buffer_ms = buffer_ms


def pcm16_mono(*samples: int) -> bytes:
    return b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in samples)


def fake_native() -> types.SimpleNamespace:
    def validate(
        sample_rate: int,
        channels: int,
        pcm16: bytes,
    ) -> tuple[int, int, int, float]:
        if sample_rate <= 0 or channels <= 0 or not pcm16 or len(pcm16) % 2:
            raise ValueError("invalid microphone PCM16")
        sample_count = len(pcm16) // 2
        if sample_count % channels:
            raise ValueError("partial microphone channel frame")
        frame_count = sample_count // channels
        return sample_rate, channels, frame_count, frame_count / sample_rate * 1000.0

    return types.SimpleNamespace(
        MicrophoneCapture=FakeNativeCapture,
        list_microphone_devices=lambda: [(0, "Default mic", True), (1, "USB mic", False)],
        native_microphone_input_supported=lambda: True,
        validate_microphone_pcm16=validate,
    )


def test_microphone_device_discovery_and_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())

    assert native_microphone_input_supported() is True
    assert microphone_devices() == (
        MicrophoneDevice(0, "Default mic", True),
        MicrophoneDevice(1, "USB mic", False),
    )


def test_microphone_chunk_is_native_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    chunk = MicrophoneChunk(1_000, 1, pcm16_mono(10, -10, 20, -20))

    assert chunk.frame_count == 4
    assert chunk.duration_ms == pytest.approx(4.0)


def test_microphone_input_reads_bounded_pcm_and_controls_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    capture = RecordingCapture()
    microphone = MicrophoneInput(capture=capture)

    assert microphone.device_name == "Test microphone"
    assert microphone.available_frames == 4
    assert microphone.dropped_frames == 3
    chunk = microphone.read(2)
    assert chunk is not None
    assert chunk.pcm16 == pcm16_mono(10, -10)

    microphone.pause()
    assert microphone.active is False
    microphone.resume()
    assert microphone.active is True
    microphone.clear()
    assert capture.clear_calls == 1
    assert microphone.read() is None

    microphone.close()
    assert microphone.closed is True
    with pytest.raises(RuntimeError, match="closed"):
        microphone.resume()


def test_microphone_input_creates_native_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    microphone = MicrophoneInput(1, buffer_ms=750)

    capture = microphone._capture
    assert isinstance(capture, FakeNativeCapture)
    assert capture.index == 1
    assert capture.buffer_ms == 750


def test_microphone_input_rejects_invalid_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())

    with pytest.raises(ValueError, match="device_index"):
        MicrophoneInput(-1, capture=RecordingCapture())
    with pytest.raises(ValueError, match="buffer_ms"):
        MicrophoneInput(buffer_ms=49, capture=RecordingCapture())

    microphone = MicrophoneInput(capture=RecordingCapture())
    with pytest.raises(ValueError, match="max_frames"):
        microphone.read(0)
