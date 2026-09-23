from __future__ import annotations

import sys
import types

import pytest

from swirui.audio import AudioClip, AudioPlayer, audio_clip_from_pcm16


class RecordingOutput:
    def __init__(self, duration_ms: float) -> None:
        self._duration_ms = duration_ms
        self._position_ms = 0.0
        self._playing = False
        self._volume = 1.0
        self._playback_rate = 1.0
        self.calls: list[tuple[str, float | None]] = []

    def play(self) -> None:
        self._playing = True
        self.calls.append(("play", None))

    def pause(self) -> None:
        self._playing = False
        self.calls.append(("pause", None))

    def stop(self) -> None:
        self._playing = False
        self._position_ms = 0.0
        self.calls.append(("stop", None))

    def seek_ms(self, elapsed_ms: float) -> float:
        self._position_ms = elapsed_ms
        self.calls.append(("seek", elapsed_ms))
        return elapsed_ms

    def position_ms(self) -> float:
        return self._position_ms

    def is_playing(self) -> bool:
        return self._playing

    def set_volume(self, volume: float) -> None:
        self._volume = volume
        self.calls.append(("volume", volume))

    def volume(self) -> float:
        return self._volume

    def set_playback_rate(self, playback_rate: float) -> None:
        self._playback_rate = playback_rate
        self.calls.append(("rate", playback_rate))

    def playback_rate(self) -> float:
        return self._playback_rate

    def duration_ms(self) -> float:
        return self._duration_ms


def fake_native() -> types.SimpleNamespace:
    def validate(
        sample_rate: int,
        channels: int,
        pcm16: bytes,
    ) -> tuple[int, int, int, float]:
        if sample_rate <= 0 or channels <= 0 or not pcm16 or len(pcm16) % 2:
            raise ValueError("invalid PCM16")
        sample_count = len(pcm16) // 2
        if sample_count % channels:
            raise ValueError("partial channel frame")
        frame_count = sample_count // channels
        return (
            sample_rate,
            channels,
            frame_count,
            frame_count / sample_rate * 1000.0,
        )

    def frame_index(
        elapsed_ms: float,
        sample_rate: int,
        frame_count: int,
        loop_audio: bool,
    ) -> int:
        if elapsed_ms < 0.0:
            raise ValueError("negative time")
        index = int(elapsed_ms / 1000.0 * sample_rate)
        if loop_audio:
            return index % frame_count
        return min(index, frame_count - 1)

    return types.SimpleNamespace(
        validate_audio_pcm16=validate,
        audio_frame_index=frame_index,
        native_audio_output_supported=lambda: False,
    )


def pcm16_mono(*samples: int) -> bytes:
    return b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in samples)


def test_audio_player_public_module_exports() -> None:
    from swirui.audio import AudioClip as PublicAudioClip
    from swirui.audio import AudioPlayer as PublicAudioPlayer

    assert PublicAudioClip is AudioClip
    assert PublicAudioPlayer is AudioPlayer


def test_audio_clip_uses_native_timeline_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = audio_clip_from_pcm16(1_000, 1, pcm16_mono(0, 100, -100, 0))

    assert clip.frame_count == 4
    assert clip.duration_ms == pytest.approx(4.0)
    assert clip.frame_index_at(0.0) == 0
    assert clip.frame_index_at(1.0) == 1
    assert clip.frame_index_at(4.0) == 0
    assert clip.frame_index_at(4.0, loop=False) == 3


def test_audio_player_controls_injected_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = audio_clip_from_pcm16(1_000, 1, pcm16_mono(0, 100, -100, 0))
    output = RecordingOutput(clip.duration_ms)
    player = AudioPlayer(
        clip,
        output=output,
        autoplay=False,
        volume=0.5,
        playback_rate=1.25,
    )

    assert player.playing is False
    player.play()
    assert player.playing is True
    player.seek(2.0)
    assert player.position_ms == pytest.approx(2.0)
    player.volume = 0.75
    player.playback_rate = 1.5
    player.pause()
    assert player.playing is False
    assert output.volume() == pytest.approx(0.75)
    assert output.playback_rate() == pytest.approx(1.5)
    player.stop()
    assert player.position_ms == pytest.approx(0.0)


def test_looping_audio_seek_wraps_to_clip_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = audio_clip_from_pcm16(1_000, 1, pcm16_mono(0, 100, -100, 0))
    output = RecordingOutput(clip.duration_ms)
    player = AudioPlayer(clip, output=output, loop=True)

    player.seek(10.0)
    assert player.position_ms == pytest.approx(2.0)


def test_audio_player_rejects_invalid_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = audio_clip_from_pcm16(1_000, 1, pcm16_mono(0, 100))
    output = RecordingOutput(clip.duration_ms)
    player = AudioPlayer(clip, output=output)

    with pytest.raises(ValueError, match="volume"):
        player.volume = 4.1
    with pytest.raises(ValueError, match="playback_rate"):
        player.playback_rate = 0.0
    with pytest.raises(ValueError, match="non-negative"):
        player.seek(-1.0)


def test_audio_clip_rejects_partial_channel_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())

    with pytest.raises(ValueError, match="partial channel frame"):
        audio_clip_from_pcm16(48_000, 2, pcm16_mono(100))
