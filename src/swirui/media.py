"""Python-first media decoding backed by SwirUI's native Rust core."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
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


@dataclass(frozen=True, slots=True)
class LottieComposition:
    """Validated Lottie composition rendered frame-by-frame by the Rust core.

    The native renderer currently supports solid layers and flat rectangle/ellipse
    shape layers with fill, position, anchor, scale and opacity keyframes. Unknown
    Lottie layer types remain isolated rather than being mis-rendered.
    """

    data: bytes
    width: int
    height: int
    frame_rate: float
    in_point: float
    out_point: float
    layer_count: int

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("Lottie composition data cannot be empty.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Lottie dimensions must be greater than zero.")
        if not isfinite(self.frame_rate) or self.frame_rate <= 0.0:
            raise ValueError("Lottie frame_rate must be finite and positive.")
        if not isfinite(self.in_point) or not isfinite(self.out_point):
            raise ValueError("Lottie frame bounds must be finite.")
        if self.out_point <= self.in_point:
            raise ValueError("Lottie out_point must be greater than in_point.")
        if self.layer_count < 0:
            raise ValueError("Lottie layer_count cannot be negative.")

    @property
    def duration_frames(self) -> float:
        return self.out_point - self.in_point

    @property
    def duration_ms(self) -> float:
        return self.duration_frames / self.frame_rate * 1000.0

    def frame_for_elapsed(self, elapsed_ms: float, *, loop: bool = True) -> float:
        """Map elapsed milliseconds to a deterministic composition frame."""

        if not isfinite(elapsed_ms) or elapsed_ms < 0.0:
            raise ValueError("elapsed_ms must be finite and non-negative.")
        offset = elapsed_ms / 1000.0 * self.frame_rate
        if loop:
            offset %= self.duration_frames
            return self.in_point + offset
        return min(self.in_point + offset, max(self.in_point, self.out_point - 1e-9))

    def render_frame(
        self,
        frame: float,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> ImageFrame:
        """Rasterize one composition frame through the bounded native core."""

        if not isfinite(frame):
            raise ValueError("frame must be finite.")
        if width is not None and width <= 0:
            raise ValueError("width must be greater than zero.")
        if height is not None and height <= 0:
            raise ValueError("height must be greater than zero.")
        native = _native_module()
        frame_width, frame_height, rgba = native.render_lottie_frame_rgba(
            self.data, float(frame), width, height
        )
        return ImageFrame(int(frame_width), int(frame_height), bytes(rgba))

    def render_at(
        self,
        elapsed_ms: float,
        *,
        loop: bool = True,
        width: int | None = None,
        height: int | None = None,
    ) -> ImageFrame:
        """Rasterize the frame selected by elapsed playback time."""

        return self.render_frame(
            self.frame_for_elapsed(elapsed_ms, loop=loop),
            width=width,
            height=height,
        )

    def register_at(
        self,
        renderer: ImageResourceRegistrar,
        resource_id: str,
        elapsed_ms: float,
        *,
        loop: bool = True,
        width: int | None = None,
        height: int | None = None,
    ) -> ImageFrame:
        """Render and transactionally rebind one logical GPU image resource."""

        if not resource_id.strip():
            raise ValueError("resource_id cannot be empty.")
        frame = self.render_at(elapsed_ms, loop=loop, width=width, height=height)
        renderer.register_image_rgba(resource_id, frame.width, frame.height, frame.rgba)
        return frame


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


def decode_lottie(data: bytes | bytearray | memoryview) -> LottieComposition:
    """Validate Lottie JSON and expose native metadata through a Python-first API."""

    payload = bytes(data)
    if not payload:
        raise ValueError("Lottie data cannot be empty.")
    native = _native_module()
    width, height, frame_rate, in_point, out_point, layer_count = native.parse_lottie_metadata(
        payload
    )
    return LottieComposition(
        payload,
        int(width),
        int(height),
        float(frame_rate),
        float(in_point),
        float(out_point),
        int(layer_count),
    )


def load_lottie(path: str | os.PathLike[str]) -> LottieComposition:
    """Load a local Bodymovin/Lottie JSON composition."""

    return decode_lottie(Path(path).read_bytes())


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
    "LottieComposition",
    "MediaFormat",
    "decode_image",
    "decode_lottie",
    "load_image",
    "load_lottie",
]
