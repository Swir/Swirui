"""Retained VideoPlayer widget backed by native timeline selection and wgpu images."""

from __future__ import annotations

from math import isfinite

from swirui.media import ImageResourceRegistrar
from swirui.rendering.geometry import Rect
from swirui.video import VideoClip

from .image import Image, ImageFit


class VideoPlayer(Image):
    """Play decoded RGBA video frames through SwirUI's persistent image registry.

    ``tick`` is scheduler-neutral and deterministic. Runtimes can advance it from
    their frame clock while applications can seek, pause and resume explicitly.
    Frame timing is resolved in Rust and presentation reuses the existing wgpu
    image resource path instead of recreating retained scene nodes per frame.
    """

    def __init__(
        self,
        clip: VideoClip,
        renderer: ImageResourceRegistrar,
        resource_id: str,
        *,
        bounds: Rect,
        fit: ImageFit = ImageFit.CONTAIN,
        loop: bool = False,
        autoplay: bool = True,
        playback_rate: float = 1.0,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._clip = clip
        self._renderer = renderer
        self._loop = bool(loop)
        self._playing = bool(autoplay)
        self._elapsed_ms = 0.0
        self._playback_rate = self._validate_playback_rate(playback_rate)
        frame = clip.register_at(renderer, resource_id, 0.0, loop=self._loop)
        super().__init__(
            resource_id,
            pixel_width=frame.width,
            pixel_height=frame.height,
            bounds=bounds,
            fit=fit,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    @property
    def clip(self) -> VideoClip:
        return self._clip

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed_ms

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def loop(self) -> bool:
        return self._loop

    @property
    def playback_rate(self) -> float:
        return self._playback_rate

    @playback_rate.setter
    def playback_rate(self, value: float) -> None:
        self._playback_rate = self._validate_playback_rate(value)

    def play(self) -> VideoPlayer:
        if not self._loop and self._elapsed_ms >= self._clip.duration_ms:
            self._elapsed_ms = 0.0
        self._playing = True
        return self

    def pause(self) -> VideoPlayer:
        self._playing = False
        return self

    def seek(self, elapsed_ms: float) -> VideoPlayer:
        """Seek to an absolute clip time and refresh the persistent GPU resource."""

        if not isfinite(elapsed_ms) or elapsed_ms < 0.0:
            raise ValueError("elapsed_ms must be finite and non-negative.")
        target = float(elapsed_ms)
        if not self._loop:
            target = min(target, self._clip.duration_ms)
        frame = self._clip.register_at(
            self._renderer,
            self.resource_id,
            target,
            loop=self._loop,
        )
        self._elapsed_ms = target
        self.set_pixel_size(frame.width, frame.height)
        self.invalidate(reason="video_frame")
        return self

    def tick(self, delta_ms: float) -> VideoPlayer:
        """Advance playback using a runtime-provided frame-clock delta."""

        if not isfinite(delta_ms) or delta_ms < 0.0:
            raise ValueError("delta_ms must be finite and non-negative.")
        if not self._playing or delta_ms == 0.0:
            return self
        target = self._elapsed_ms + float(delta_ms) * self._playback_rate
        self.seek(target)
        if not self._loop and target >= self._clip.duration_ms:
            self._playing = False
        return self

    @staticmethod
    def _validate_playback_rate(value: float) -> float:
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0.0 or normalized > 16.0:
            raise ValueError("playback_rate must be finite and in the range (0, 16].")
        return normalized


__all__ = ["VideoPlayer"]
