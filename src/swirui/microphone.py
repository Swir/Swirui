"""Python-first microphone input backed by SwirUI's native Rust core."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Protocol, cast


@dataclass(frozen=True, slots=True)
class MicrophoneDevice:
    """One native microphone input device exposed by SwirUI."""

    index: int
    name: str
    is_default: bool = False


@dataclass(frozen=True, slots=True)
class MicrophoneChunk:
    """One validated little-endian interleaved PCM16 microphone chunk."""

    sample_rate: int
    channels: int
    pcm16: bytes

    def __post_init__(self) -> None:
        normalized = bytes(self.pcm16)
        object.__setattr__(self, "pcm16", normalized)
        _native_module().validate_microphone_pcm16(
            int(self.sample_rate),
            int(self.channels),
            normalized,
        )

    @property
    def frame_count(self) -> int:
        return len(self.pcm16) // 2 // self.channels

    @property
    def duration_ms(self) -> float:
        return self.frame_count / self.sample_rate * 1000.0


class MicrophoneCaptureBackend(Protocol):
    """Minimal native/injected capture contract used by :class:`MicrophoneInput`."""

    @property
    def sample_rate(self) -> int: ...

    @property
    def channels(self) -> int: ...

    @property
    def device_name(self) -> str: ...

    @property
    def is_open(self) -> bool: ...

    @property
    def is_active(self) -> bool: ...

    def read_pcm16(self, max_frames: int | None = None) -> bytes: ...

    def available_frames(self) -> int: ...

    def dropped_frames(self) -> int: ...

    def clear(self) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def close(self) -> None: ...

    def last_error(self) -> str | None: ...


class MicrophoneInput:
    """Bounded microphone capture with a Python-first PCM16 API.

    The default backend is the native Windows CPAL/WASAPI stream owned by the
    Rust/PyO3 core. Applications can inject a compatible backend for tests or
    specialized devices without changing the public control surface.
    """

    def __init__(
        self,
        device_index: int | None = None,
        *,
        buffer_ms: int = 2_000,
        capture: MicrophoneCaptureBackend | None = None,
    ) -> None:
        if device_index is not None and device_index < 0:
            raise ValueError("device_index cannot be negative.")
        if buffer_ms < 50 or buffer_ms > 10_000:
            raise ValueError("buffer_ms must be in the range [50, 10000].")
        self._capture = capture or _create_native_capture(device_index, buffer_ms)
        self._closed = False

    @property
    def sample_rate(self) -> int:
        return int(self._capture.sample_rate)

    @property
    def channels(self) -> int:
        return int(self._capture.channels)

    @property
    def device_name(self) -> str:
        return str(self._capture.device_name)

    @property
    def closed(self) -> bool:
        return self._closed or not bool(self._capture.is_open)

    @property
    def active(self) -> bool:
        return not self.closed and bool(self._capture.is_active)

    @property
    def available_frames(self) -> int:
        if self.closed:
            return 0
        return int(self._capture.available_frames())

    @property
    def dropped_frames(self) -> int:
        return int(self._capture.dropped_frames())

    @property
    def last_error(self) -> str | None:
        return self._capture.last_error()

    def read(self, max_frames: int | None = None) -> MicrophoneChunk | None:
        """Drain up to ``max_frames`` from the bounded native ring buffer."""

        self._ensure_open()
        if max_frames is not None and max_frames <= 0:
            raise ValueError("max_frames must be greater than zero when provided.")
        pcm16 = bytes(self._capture.read_pcm16(max_frames))
        if not pcm16:
            return None
        return MicrophoneChunk(self.sample_rate, self.channels, pcm16)

    def clear(self) -> MicrophoneInput:
        self._ensure_open()
        self._capture.clear()
        return self

    def pause(self) -> MicrophoneInput:
        self._ensure_open()
        self._capture.pause()
        return self

    def resume(self) -> MicrophoneInput:
        self._ensure_open()
        self._capture.resume()
        return self

    def close(self) -> None:
        if self._closed:
            return
        self._capture.close()
        self._closed = True

    def __enter__(self) -> MicrophoneInput:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeError("Microphone input is closed.")


def microphone_devices() -> tuple[MicrophoneDevice, ...]:
    """Return input devices discovered by the verified native backend."""

    devices = _native_module().list_microphone_devices()
    return tuple(
        MicrophoneDevice(int(index), str(name), bool(is_default))
        for index, name, is_default in devices
    )


def native_microphone_input_supported() -> bool:
    """Whether this native build exposes the verified microphone backend."""

    return bool(_native_module().native_microphone_input_supported())


def _create_native_capture(
    device_index: int | None,
    buffer_ms: int,
) -> MicrophoneCaptureBackend:
    native = _native_module()
    if not bool(native.native_microphone_input_supported()):
        raise RuntimeError(
            "SwirUI native microphone input is currently available on Windows builds."
        )
    capture_type = getattr(native, "MicrophoneCapture", None)
    if capture_type is None:
        raise RuntimeError(
            "SwirUI native microphone input is missing. Rebuild native/ with Maturin."
        )
    capture = capture_type(device_index, int(buffer_ms))
    return cast(MicrophoneCaptureBackend, capture)


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native microphone core is not installed. Build/install native/ with Maturin."
        ) from exc


__all__ = [
    "MicrophoneCaptureBackend",
    "MicrophoneChunk",
    "MicrophoneDevice",
    "MicrophoneInput",
    "microphone_devices",
    "native_microphone_input_supported",
]
