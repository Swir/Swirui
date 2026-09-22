from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="native VideoPlayer gate is Windows-only",
)


def solid(red: int) -> bytes:
    return bytes((red, 0, 0, 255)) * 2


def test_native_video_metadata_and_timeline_selection() -> None:
    import _swirui_native as native

    frames = [solid(10), solid(20), solid(30)]
    metadata = native.validate_video_rgba_frames(2, 1, 2.0, frames)
    assert metadata[:4] == (2, 1, 2.0, 3)
    assert metadata[4] == pytest.approx(1500.0)

    assert native.video_frame_index(0.0, 2.0, 3, True) == 0
    assert native.video_frame_index(500.0, 2.0, 3, True) == 1
    assert native.video_frame_index(1500.0, 2.0, 3, True) == 0
    assert native.video_frame_index(1500.0, 2.0, 3, False) == 2


def test_python_video_player_drives_native_timeline_and_gpu_resource() -> None:
    from swirui import VideoPlayer
    from swirui.rendering import Rect
    from swirui.video import video_clip_from_rgba_frames

    class Renderer:
        def __init__(self) -> None:
            self.frames: list[bytes] = []

        def register_image_rgba(
            self,
            resource_id: str,
            width: int,
            height: int,
            rgba: bytes | bytearray | memoryview,
        ) -> None:
            assert resource_id == "native:video"
            assert (width, height) == (2, 1)
            self.frames.append(bytes(rgba))

    clip = video_clip_from_rgba_frames(2, 1, 2.0, (solid(10), solid(20), solid(30)))
    renderer = Renderer()
    player = VideoPlayer(
        clip,
        renderer,
        "native:video",
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        loop=True,
    )

    player.tick(500.0)
    player.tick(500.0)
    assert renderer.frames == [solid(10), solid(20), solid(30)]
