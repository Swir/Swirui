from __future__ import annotations

import sys
import types

import pytest

from swirui.media import ImageFrame
from swirui.rendering import Rect
from swirui.video import VideoClip, video_clip_from_rgba_frames
from swirui.widgets.video_player import VideoPlayer


class Renderer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int, bytes]] = []

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None:
        self.calls.append((resource_id, width, height, bytes(rgba)))


def fake_native() -> types.SimpleNamespace:
    def validate(
        width: int,
        height: int,
        frame_rate: float,
        frames: list[bytes],
    ) -> tuple[int, int, float, int, float]:
        if width <= 0 or height <= 0 or not frames:
            raise ValueError("invalid video")
        expected = width * height * 4
        if any(len(frame) != expected for frame in frames):
            raise ValueError("invalid RGBA frame")
        return width, height, frame_rate, len(frames), len(frames) / frame_rate * 1000.0

    def frame_index(
        elapsed_ms: float,
        frame_rate: float,
        frame_count: int,
        loop_video: bool,
    ) -> int:
        if elapsed_ms < 0.0:
            raise ValueError("negative time")
        index = int(elapsed_ms / 1000.0 * frame_rate)
        if loop_video:
            return index % frame_count
        return min(index, frame_count - 1)

    return types.SimpleNamespace(
        validate_video_rgba_frames=validate,
        video_frame_index=frame_index,
    )


def solid(red: int) -> bytes:
    return bytes((red, 0, 0, 255)) * 2


def test_video_player_is_exported_from_public_api() -> None:
    from swirui import VideoPlayer as PublicVideoPlayer

    assert PublicVideoPlayer is VideoPlayer


def test_video_clip_uses_native_timeline_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = video_clip_from_rgba_frames(2, 1, 2.0, (solid(10), solid(20), solid(30)))

    assert clip.frame_count == 3
    assert clip.duration_ms == pytest.approx(1500.0)
    assert clip.frame_index_at(0.0) == 0
    assert clip.frame_index_at(500.0) == 1
    assert clip.frame_index_at(1500.0) == 0
    assert clip.frame_index_at(1500.0, loop=False) == 2


def test_video_player_rebinds_persistent_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = VideoClip(
        (
            ImageFrame(2, 1, solid(10)),
            ImageFrame(2, 1, solid(20)),
            ImageFrame(2, 1, solid(30)),
        ),
        2.0,
    )
    renderer = Renderer()
    player = VideoPlayer(
        clip,
        renderer,
        "demo:video",
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        loop=True,
    )

    assert player.pixel_size == (2, 1)
    assert renderer.calls[0][0] == "demo:video"
    player.tick(500.0)
    assert player.elapsed_ms == pytest.approx(500.0)
    assert renderer.calls[-1][3] == solid(20)

    player.pause().tick(500.0)
    assert player.elapsed_ms == pytest.approx(500.0)
    player.play().seek(1000.0)
    assert renderer.calls[-1][3] == solid(30)


def test_non_looping_video_stops_at_end(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = video_clip_from_rgba_frames(2, 1, 2.0, (solid(10), solid(20), solid(30)))
    renderer = Renderer()
    player = VideoPlayer(
        clip,
        renderer,
        "demo:video",
        bounds=Rect(0.0, 0.0, 100.0, 50.0),
        loop=False,
    )

    player.tick(2000.0)
    assert player.elapsed_ms == pytest.approx(1500.0)
    assert player.playing is False
    assert renderer.calls[-1][3] == solid(30)


def test_video_clip_rejects_mixed_frame_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())

    with pytest.raises(ValueError, match="identical dimensions"):
        VideoClip((ImageFrame(2, 1, solid(10)), ImageFrame(1, 1, bytes(4))), 30.0)


def test_video_player_rejects_invalid_clock_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    clip = video_clip_from_rgba_frames(2, 1, 2.0, (solid(10),))
    player = VideoPlayer(
        clip,
        Renderer(),
        "demo:video",
        bounds=Rect(0.0, 0.0, 100.0, 50.0),
    )

    with pytest.raises(ValueError, match="non-negative"):
        player.tick(-1.0)
