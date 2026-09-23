"""Retained CameraView widget for live native or application-provided frames."""

from __future__ import annotations

from swirui.camera import CameraSource, validate_camera_frame
from swirui.media import ImageFrame, ImageResourceRegistrar
from swirui.rendering.geometry import Rect

from .image import Image, ImageFit


class CameraView(Image):
    """Present live RGBA camera frames through one persistent wgpu image resource."""

    def __init__(
        self,
        source: CameraSource,
        renderer: ImageResourceRegistrar,
        resource_id: str,
        *,
        bounds: Rect,
        fit: ImageFit = ImageFit.COVER,
        active: bool = True,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = True,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._source = source
        self._renderer = renderer
        self._active = bool(active)
        self._closed = False
        frame = self._capture_frame(resource_id)
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
    def active(self) -> bool:
        return self._active and not self._closed

    @property
    def closed(self) -> bool:
        return self._closed

    def refresh(self) -> CameraView:
        """Capture and upload one fresh frame when the view is active."""

        if not self.active:
            return self
        frame = self._capture_frame(self.resource_id)
        self.set_pixel_size(frame.width, frame.height)
        self.invalidate(reason="camera_frame")
        return self

    def pause(self) -> CameraView:
        self._active = False
        return self

    def resume(self) -> CameraView:
        if self._closed:
            raise RuntimeError("CameraView is closed.")
        self._active = True
        return self

    def close(self) -> None:
        if self._closed:
            return
        self._source.close()
        self._closed = True
        self._active = False

    def _capture_frame(self, resource_id: str) -> ImageFrame:
        frame = self._source.read_frame()
        validate_camera_frame(frame)
        self._renderer.register_image_rgba(
            resource_id,
            frame.width,
            frame.height,
            frame.rgba,
        )
        return frame


__all__ = ["CameraView"]
