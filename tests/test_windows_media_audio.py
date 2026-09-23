from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="native AudioPlayer gate is Windows-only",
)


def pcm16_stereo(*frames: tuple[int, int]) -> bytes:
    return b"".join(
        int(sample).to_bytes(2, "little", signed=True)
        for frame in frames
        for sample in frame
    )


def test_native_audio_metadata_timeline_and_output_class() -> None:
    import _swirui_native as native

    pcm16 = pcm16_stereo((0, 0), (1000, -1000), (0, 0))
    metadata = native.validate_audio_pcm16(48_000, 2, pcm16)
    assert metadata[:3] == (48_000, 2, 3)
    assert metadata[3] == pytest.approx(3.0 / 48_000.0 * 1000.0)

    assert native.audio_frame_index(0.0, 1_000, 3, True) == 0
    assert native.audio_frame_index(1.0, 1_000, 3, True) == 1
    assert native.audio_frame_index(3.0, 1_000, 3, True) == 0
    assert native.audio_frame_index(3.0, 1_000, 3, False) == 2
    assert native.native_audio_output_supported() is True
    assert hasattr(native, "AudioOutput")


def test_python_audio_player_controls_native_qualified_clip() -> None:
    from swirui.audio import AudioPlayer, audio_clip_from_pcm16

    class Output:
        def __init__(self) -> None:
            self.position = 0.0
            self.playing = False
            self.current_volume = 1.0
            self.current_rate = 1.0

        def play(self) -> None:
            self.playing = True

        def pause(self) -> None:
            self.playing = False

        def stop(self) -> None:
            self.playing = False
            self.position = 0.0

        def seek_ms(self, elapsed_ms: float) -> float:
            self.position = elapsed_ms
            return elapsed_ms

        def position_ms(self) -> float:
            return self.position

        def is_playing(self) -> bool:
            return self.playing

        def set_volume(self, volume: float) -> None:
            self.current_volume = volume

        def volume(self) -> float:
            return self.current_volume

        def set_playback_rate(self, playback_rate: float) -> None:
            self.current_rate = playback_rate

        def playback_rate(self) -> float:
            return self.current_rate

        def duration_ms(self) -> float:
            return 3.0

    clip = audio_clip_from_pcm16(
        1_000,
        1,
        b"\x00\x00\xe8\x03\x18\xfc",
    )
    output = Output()
    player = AudioPlayer(
        clip,
        output=output,
        autoplay=False,
        volume=0.5,
        playback_rate=1.25,
    )

    player.play().seek(2.0)
    assert player.playing is True
    assert player.position_ms == pytest.approx(2.0)
    assert output.current_volume == pytest.approx(0.5)
    assert output.current_rate == pytest.approx(1.25)
