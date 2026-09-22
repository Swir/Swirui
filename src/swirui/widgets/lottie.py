"""Playback-oriented Lottie widget backed by native frame rasterization."""

from __future__ import annotations

from swirui.media import ImageResourceRegistrar, LottieComposition
from swirui.rendering.geometry import Rect

from .image import Image, ImageFit


class Lottie(Image):
    """Render a Lottie composition into the persistent GPU image registry.

    ``tick`` is deterministic and scheduler-neutral: runtimes can advance the
    widget from their frame clock while tests and tools can seek exact times.
    Native frame rasterization is isolated behind ``LottieComposition`` and the
    resulting RGBA resource reuses the existing content-addressed wgpu cache.
    """

    def __init__(
        self,
        composition: LottieComposition,
        renderer: ImageResourceRegistrar,
        resource_id: str,
        *,
        bounds: Rect,
        fit: ImageFit = ImageFit.CONTAIN,
        loop: bool = True,
        autoplay: bool = True,
        render_width: int | None = None,
        render_height: int | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        if render_width is not None and render_width <= 0:
            raise ValueError("render_width must be greater than zero.")
        if render_height is not None and render_height <= 0:
            raise ValueError("render_height must be greater than zero.")
        self._composition = composition
        self._renderer = renderer
        self._loop = bool(loop)
        self._playing = bool(autoplay)
        self._elapsed_ms = 0.0
        self._render_width = render_width
        self._render_height = render_height
        frame = composition.register_at(
            renderer,
            resource_id,
            0.0,
            loop=self._loop,
            width=render_width,
            height=render_height,
        )
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
    def composition(self) -> LottieComposition:
        return self._composition

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed_ms

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def loop(self) -> bool:
        return self._loop

    def play(self) -> Lottie:
        self._playing = True
        return self

    def pause(self) -> Lottie:
        self._playing = False
        return self

    def seek(self, elapsed_ms: float) -> Lottie:
        frame = self._composition.register_at(
            self._renderer,
            self.resource_id,
            elapsed_ms,
            loop=self._loop,
            width=self._render_width,
            height=self._render_height,
        )
        self._elapsed_ms = float(elapsed_ms)
        self.set_pixel_size(frame.width, frame.height)
        self.invalidate(reason="lottie_frame")
        return self

    def tick(self, delta_ms: float) -> Lottie:
        """Advance playback from a runtime frame clock when currently playing."""

        if delta_ms < 0.0:
            raise ValueError("delta_ms cannot be negative.")
        if self._playing and delta_ms > 0.0:
            self.seek(self._elapsed_ms + delta_ms)
        return self


__all__ = ["Lottie"]
