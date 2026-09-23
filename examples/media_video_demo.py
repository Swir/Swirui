"""Minimal deterministic VideoPlayer example for the native RGBA playback path."""

from __future__ import annotations

from swirui import VideoPlayer
from swirui.rendering import Rect
from swirui.video import video_clip_from_rgba_frames


class DemoRenderer:
    """Small stand-in for the runtime image registry used by this isolated example."""

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None:
        print(f"registered {resource_id}: {width}x{height}, {len(rgba)} RGBA bytes")


def solid(red: int, green: int, blue: int) -> bytes:
    return bytes((red, green, blue, 255)) * (4 * 3)


def main() -> None:
    clip = video_clip_from_rgba_frames(
        4,
        3,
        2.0,
        (
            solid(255, 40, 40),
            solid(40, 255, 80),
            solid(40, 100, 255),
        ),
    )
    player = VideoPlayer(
        clip,
        DemoRenderer(),
        "demo:video",
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
        loop=True,
        accessible_name="Video preview",
    )
    player.tick(500.0)
    player.tick(500.0)
    player.pause().seek(0.0)


if __name__ == "__main__":
    main()
