"""Python-first PCM audio playback backed by SwirUI's native Rust core."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Any, Protocol, cast

from .core import Component

if TYPE_CHECKING:
    from .window import Window


class AudioOutputBackend(Protocol):
    """Minimal output contract used by :class:`AudioPlayer`."""

    def play(self) -> None: ...

    def pause(self) -> None: ...

    def stop(self) -> None: ...

    def seek_ms(self, elapsed_ms: float) -> float: ...

    def position_ms(self) -> float: ...

    def is_playing(self) -> bool: ...

    def set_volume(self, volume: float) -> None: ...

    def volume(self) -> float: ...

    def set_playback_rate(self, playback_rate: float) -> None: ...

    def playback_rate(self) -> float: ...

    def duration_ms(self) -> float: ...


@dataclass(frozen=True, slots=True)
class AudioClip:
    """Validated little-endian interleaved signed PCM16 audio."""

    sample_rate: int
    channels: int
    pcm16: bytes

    def __post_init__(self) -> None:
        normalized = bytes(self.pcm16)
        object.__setattr__(self, "pcm16", normalized)
        native = _native_module()
        native.validate_audio_pcm16(
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

    def frame_index_at(self, elapsed_ms: float, *, loop: bool = True) -> int:
        """Resolve playback time to a bounded native PCM frame index."""

        native = _native_module()
        return int(
            native.audio_frame_index(
                float(elapsed_ms),
                int(self.sample_rate),
                self.frame_count,
                bool(loop),
            )
        )


class AudioPlayer(Component):
    """Retained logical audio player using the native Windows output backend.

    Applications may inject an ``AudioOutputBackend`` for deterministic tests or
    custom devices. The default output is created by the Rust/PyO3 core and owns
    the OS audio stream while this Python object remains the public control API.
    """

    def __init__(
        self,
        clip: AudioClip,
        *,
        output: AudioOutputBackend | None = None,
        loop: bool = False,
        autoplay: bool = True,
        volume: float = 1.0,
        playback_rate: float = 1.0,
        name: str | None = None,
        key: str | None = None,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            name,
            key=key,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._clip = clip
        self._loop = bool(loop)
        self._volume = self._validate_volume(volume)
        self._playback_rate = self._validate_playback_rate(playback_rate)
        self._output = output or _create_native_output(
            clip,
            loop=self._loop,
            autoplay=autoplay,
            volume=self._volume,
            playback_rate=self._playback_rate,
        )
        self._output.set_volume(self._volume)
        self._output.set_playback_rate(self._playback_rate)
        if autoplay:
            self._output.play()
        else:
            self._output.pause()

    @property
    def clip(self) -> AudioClip:
        return self._clip

    @property
    def loop(self) -> bool:
        return self._loop

    @property
    def duration_ms(self) -> float:
        return self._clip.duration_ms

    @property
    def position_ms(self) -> float:
        return float(self._output.position_ms())

    @property
    def playing(self) -> bool:
        return bool(self._output.is_playing())

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        normalized = self._validate_volume(value)
        if normalized == self._volume:
            return
        self._volume = normalized
        self._output.set_volume(normalized)
        self.invalidate(reason="audio_volume")

    @property
    def playback_rate(self) -> float:
        return self._playback_rate

    @playback_rate.setter
    def playback_rate(self, value: float) -> None:
        normalized = self._validate_playback_rate(value)
        if normalized == self._playback_rate:
            return
        self._playback_rate = normalized
        self._output.set_playback_rate(normalized)
        self.invalidate(reason="audio_playback_rate")

    def play(self) -> AudioPlayer:
        self._output.play()
        self.invalidate(reason="audio_play")
        return self

    def pause(self) -> AudioPlayer:
        self._output.pause()
        self.invalidate(reason="audio_pause")
        return self

    def stop(self) -> AudioPlayer:
        self._output.stop()
        self.invalidate(reason="audio_stop")
        return self

    def seek(self, elapsed_ms: float) -> AudioPlayer:
        if not isfinite(elapsed_ms) or elapsed_ms < 0.0:
            raise ValueError("elapsed_ms must be finite and non-negative.")
        target = float(elapsed_ms)
        if self._loop:
            target %= self._clip.duration_ms
        else:
            target = min(target, self._clip.duration_ms)
        self._output.seek_ms(target)
        self.invalidate(reason="audio_seek")
        return self

    def on_unmount(self, window: Window) -> None:
        del window
        self._output.stop()

    @staticmethod
    def _validate_volume(value: float) -> float:
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0 or normalized > 4.0:
            raise ValueError("volume must be finite and in the range [0, 4].")
        return normalized

    @staticmethod
    def _validate_playback_rate(value: float) -> float:
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.25 or normalized > 4.0:
            raise ValueError("playback_rate must be finite and in the range [0.25, 4].")
        return normalized


def audio_clip_from_pcm16(
    sample_rate: int,
    channels: int,
    pcm16: bytes | bytearray | memoryview,
) -> AudioClip:
    """Create a native-qualified clip from interleaved little-endian PCM16."""

    return AudioClip(int(sample_rate), int(channels), bytes(pcm16))


def native_audio_output_supported() -> bool:
    """Return whether this native build contains the OS audio-output backend."""

    native = _native_module()
    return bool(native.native_audio_output_supported())


def _create_native_output(
    clip: AudioClip,
    *,
    loop: bool,
    autoplay: bool,
    volume: float,
    playback_rate: float,
) -> AudioOutputBackend:
    native = _native_module()
    if not bool(native.native_audio_output_supported()):
        raise RuntimeError(
            "SwirUI native AudioPlayer output is currently available on Windows builds."
        )
    output_type = getattr(native, "AudioOutput", None)
    if output_type is None:
        raise RuntimeError(
            "SwirUI native audio output is missing. Rebuild native/ with Maturin."
        )
    output = output_type(
        int(clip.sample_rate),
        int(clip.channels),
        clip.pcm16,
        bool(loop),
        bool(autoplay),
        float(volume),
        float(playback_rate),
    )
    return cast(AudioOutputBackend, output)


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native audio core is not installed. Build/install native/ with Maturin."
        ) from exc


__all__ = [
    "AudioClip",
    "AudioOutputBackend",
    "AudioPlayer",
    "audio_clip_from_pcm16",
    "native_audio_output_supported",
]
