"""Python-first media decoding backed by SwirUI's native Rust core."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class MediaFormat(StrEnum):
    """Media formats recognized by the first SwirUI image pipeline."""

    RASTER = "raster"
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    BMP = "bmp"
    GIF = "gif"
    SVG = "svg"


class ImageResourceRegistrar(Protocol):
    """Minimal renderer contract required to upload decoded RGBA resources."""

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ImageFrame:
    """One decoded RGBA8 frame in logical animation order."""

    width: int
    height: int
    rgba: bytes
    duration_ms: int = 0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Image frame dimensions must be greater than zero.")
        if self.duration_ms < 0:
            raise ValueError("Image frame duration cannot be negative.")
        expected = self.width * self.height * 4
        if len(self.rgba) != expected:
            raise ValueError(
                f"RGBA frame requires exactly {expected} bytes for "
                f"{self.width}x{self.height}; received {len(self.rgba)}."
            )


@dataclass(frozen=True, slots=True)
class ImageAsset:
    """Decoded static or animated image ready for the persistent GPU registry."""

    format: MediaFormat
    frames: tuple[ImageFrame, ...]
    loop_count: int | None = None

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("ImageAsset requires at least one frame.")
        if self.loop_count is not None and self.loop_count < 0:
            raise ValueError("loop_count cannot be negative.")

    @property
    def width(self) -> int:
        return self.frames[0].width

    @property
    def height(self) -> int:
        return self.frames[0].height

    @property
    def animated(self) -> bool:
        return len(self.frames) > 1

    @property
    def duration_ms(self) -> int:
        if not self.animated:
            return 0
        return sum(max(frame.duration_ms, 10) for frame in self.frames)

    def frame_at(self, elapsed_ms: int) -> ImageFrame:
        """Return the frame visible at ``elapsed_ms`` using bounded GIF timing."""

        if elapsed_ms < 0:
            raise ValueError("elapsed_ms cannot be negative.")
        if not self.animated:
            return self.frames[0]

        durations = tuple(max(frame.duration_ms, 10) for frame in self.frames)
        cycle = sum(durations)
        if self.loop_count is None:
            if elapsed_ms >= cycle:
                return self.frames[-1]
            position = elapsed_ms
        elif self.loop_count == 0:
            position = elapsed_ms % cycle
        else:
            total = cycle * (self.loop_count + 1)
            if elapsed_ms >= total:
                return self.frames[-1]
            position = elapsed_ms % cycle

        cursor = 0
        for frame, duration in zip(self.frames, durations, strict=True):
            cursor += duration
            if position < cursor:
                return frame
        return self.frames[-1]

    def register_frame(
        self,
        renderer: ImageResourceRegistrar,
        resource_id: str,
        *,
        frame_index: int = 0,
    ) -> str:
        """Upload one decoded frame to the renderer's content-addressed cache."""

        if not resource_id.strip():
            raise ValueError("resource_id cannot be empty.")
        try:
            frame = self.frames[frame_index]
        except IndexError as exc:
            raise IndexError("frame_index is outside the decoded frame range.") from exc
        renderer.register_image_rgba(resource_id, frame.width, frame.height, frame.rgba)
        return resource_id

    def register_all(
        self,
        renderer: ImageResourceRegistrar,
        resource_prefix: str,
    ) -> tuple[str, ...]:
        """Upload every animation frame under deterministic resource ids."""

        if not resource_prefix.strip():
            raise ValueError("resource_prefix cannot be empty.")
        resource_ids: list[str] = []
        for index, frame in enumerate(self.frames):
            resource_id = f"{resource_prefix}:{index}"
            renderer.register_image_rgba(resource_id, frame.width, frame.height, frame.rgba)
            resource_ids.append(resource_id)
        return tuple(resource_ids)


def decode_image(
    data: bytes | bytearray | memoryview,
    *,
    format_hint: MediaFormat | str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> ImageAsset:
    """Decode PNG/JPEG/WebP/BMP, SVG or GIF bytes through the Rust media core."""

    payload = bytes(data)
    if not payload:
        raise ValueError("Image data cannot be empty.")
    media_format = (
        _normalize_format(format_hint) if format_hint is not None else _detect_format(payload)
    )
    native = _native_module()

    if media_format is MediaFormat.GIF:
        if width is not None or height is not None:
            raise ValueError("width/height overrides are currently supported only for SVG.")
        raw_frames = native.decode_gif_rgba_frames(payload)
        frames = tuple(
            ImageFrame(int(frame_width), int(frame_height), bytes(rgba), int(duration_ms))
            for frame_width, frame_height, duration_ms, rgba in raw_frames
        )
        return ImageAsset(media_format, frames, _gif_loop_count(payload))

    if media_format is MediaFormat.SVG:
        if width is not None and width <= 0:
            raise ValueError("width must be greater than zero.")
        if height is not None and height <= 0:
            raise ValueError("height must be greater than zero.")
        frame_width, frame_height, rgba = native.decode_svg_rgba(payload, width, height)
        frame = ImageFrame(int(frame_width), int(frame_height), bytes(rgba))
        return ImageAsset(media_format, (frame,))

    if width is not None or height is not None:
        raise ValueError("width/height overrides are currently supported only for SVG.")
    frame_width, frame_height, rgba = native.decode_image_rgba(payload)
    frame = ImageFrame(int(frame_width), int(frame_height), bytes(rgba))
    return ImageAsset(media_format, (frame,))


def load_image(
    path: str | os.PathLike[str],
    *,
    width: int | None = None,
    height: int | None = None,
) -> ImageAsset:
    """Load and decode a local image asset without exposing native APIs."""

    source = Path(path)
    data = source.read_bytes()
    hint = source.suffix.lower().removeprefix(".") or None
    return decode_image(data, format_hint=hint, width=width, height=height)


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native media core is not installed. Build/install native/ with Maturin."
        ) from exc


def _normalize_format(value: MediaFormat | str) -> MediaFormat:
    if isinstance(value, MediaFormat):
        return value
    normalized = str(value).strip().lower().removeprefix(".")
    aliases = {
        "jpg": MediaFormat.JPEG,
        "jpeg": MediaFormat.JPEG,
        "png": MediaFormat.PNG,
        "webp": MediaFormat.WEBP,
        "bmp": MediaFormat.BMP,
        "gif": MediaFormat.GIF,
        "svg": MediaFormat.SVG,
        "svg+xml": MediaFormat.SVG,
        "raster": MediaFormat.RASTER,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported image format hint: {value!r}.") from exc


def _detect_format(data: bytes) -> MediaFormat:
    if data.startswith((b"GIF87a", b"GIF89a")):
        return MediaFormat.GIF
    prefix = data[:4096].lstrip().lower()
    if prefix.startswith(b"<svg") or b"<svg" in prefix:
        return MediaFormat.SVG
    return MediaFormat.RASTER


def _gif_loop_count(data: bytes) -> int | None:
    for marker in (b"NETSCAPE2.0", b"ANIMEXTS1.0"):
        marker_index = data.find(marker)
        if marker_index < 0:
            continue
        start = marker_index + len(marker)
        extension = data[start : start + 8]
        marker_offset = extension.find(bytes((3, 1)))
        if marker_offset >= 0 and marker_offset + 4 <= len(extension):
            low = extension[marker_offset + 2]
            high = extension[marker_offset + 3]
            return low | (high << 8)
    return None


__all__ = [
    "ImageAsset",
    "ImageFrame",
    "ImageResourceRegistrar",
    "MediaFormat",
    "decode_image",
    "load_image",
]
