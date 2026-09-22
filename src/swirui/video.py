"""Python-first video frame playback backed by SwirUI's native Rust core."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable

from .media import ImageFrame, ImageResourceRegistrar


@dataclass(frozen=True, slots=True)
class VideoClip:
    """Validated in-memory RGBA video clip with native frame selection.

    SwirUI deliberately keeps decoded frame ownership separate from the retained
    player widget. This first video substrate accepts RGBA8 frames produced by a
    decoder or application pipeline while Rust enforces bounded dimensions,
    memory use, frame rate and deterministic timeline selection.
    """

    frames: tuple[ImageFrame, ...]
    frame_rate: float

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("VideoClip requires at least one frame.")
        if not isfinite(self.frame_rate) or self.frame_rate <= 0.0:
            raise ValueError("VideoClip frame_rate must be finite and positive.")
        width = self.frames[0].width
        height = self.frames[0].height
        if any(frame.width != width or frame.height != height for frame in self.frames):
            raise ValueError("All VideoClip frames must have identical dimensions.")
        native = _native_module()
        native.validate_video_rgba_frames(
            width,
            height,
            float(self.frame_rate),
            [frame.rgba for frame in self.frames],
        )

    @property
    def width(self) -> int:
        return self.frames[0].width

    @property
    def height(self) -> int:
        return self.frames[0].height

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration_ms(self) -> float:
        return self.frame_count / self.frame_rate * 1000.0

    def frame_index_at(self, elapsed_ms: float, *, loop: bool = True) -> int:
        """Resolve playback time to a bounded frame index in the native core."""

        native = _native_module()
        return int(
            native.video_frame_index(
                float(elapsed_ms),
                float(self.frame_rate),
                self.frame_count,
                bool(loop),
            )
        )

    def frame_at(self, elapsed_ms: float, *, loop: bool = True) -> ImageFrame:
        return self.frames[self.frame_index_at(elapsed_ms, loop=loop)]

    def register_at(
        self,
        renderer: ImageResourceRegistrar,
        resource_id: str,
        elapsed_ms: float,
        *,
        loop: bool = True,
    ) -> ImageFrame:
        """Upload the frame visible at ``elapsed_ms`` to one persistent resource."""

        if not resource_id.strip():
            raise ValueError("resource_id cannot be empty.")
        frame = self.frame_at(elapsed_ms, loop=loop)
        renderer.register_image_rgba(resource_id, frame.width, frame.height, frame.rgba)
        return frame


def video_clip_from_rgba_frames(
    width: int,
    height: int,
    frame_rate: float,
    frames: Iterable[bytes | bytearray | memoryview],
) -> VideoClip:
    """Create a native-qualified clip from decoded RGBA8 frames."""

    decoded = tuple(ImageFrame(int(width), int(height), bytes(frame)) for frame in frames)
    return VideoClip(decoded, float(frame_rate))


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native video core is not installed. Build/install native/ with Maturin."
        ) from exc


__all__ = ["VideoClip", "video_clip_from_rgba_frames"]
