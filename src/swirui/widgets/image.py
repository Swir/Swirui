"""Retained GPU image widget for SwirUI media resources."""

from __future__ import annotations

from enum import StrEnum

from swirui.core import AccessibilityRole
from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget


class ImageFit(StrEnum):
    """How decoded image pixels fit inside authored widget bounds."""

    FILL = "fill"
    CONTAIN = "contain"
    COVER = "cover"
    NONE = "none"


class Image(Widget):
    """Display one registered RGBA image resource with deterministic fitting."""

    def __init__(
        self,
        resource_id: str,
        *,
        pixel_width: int,
        pixel_height: int,
        bounds: Rect,
        fit: ImageFit = ImageFit.CONTAIN,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._resource_id = self._validate_resource_id(resource_id)
        self._pixel_width, self._pixel_height = self._validate_pixel_size(
            pixel_width, pixel_height
        )
        self._fit = ImageFit(fit)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
            accessibility_role=AccessibilityRole.IMAGE,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )

    @property
    def resource_id(self) -> str:
        return self._resource_id

    @resource_id.setter
    def resource_id(self, value: str) -> None:
        normalized = self._validate_resource_id(value)
        if normalized == self._resource_id:
            return
        self._resource_id = normalized
        self.invalidate(reason="resource_id")

    @property
    def pixel_size(self) -> tuple[int, int]:
        return self._pixel_width, self._pixel_height

    def set_pixel_size(self, width: int, height: int) -> Image:
        normalized = self._validate_pixel_size(width, height)
        if normalized != self.pixel_size:
            self._pixel_width, self._pixel_height = normalized
            self.invalidate(reason="pixel_size")
        return self

    @property
    def fit(self) -> ImageFit:
        return self._fit

    @fit.setter
    def fit(self, value: ImageFit) -> None:
        normalized = ImageFit(value)
        if normalized == self._fit:
            return
        self._fit = normalized
        self.invalidate(reason="fit")

    def intrinsic_size(self, available: Size | None = None) -> Size:
        _ = available
        return Size(
            max(self.preferred_size.width, float(self._pixel_width)),
            max(self.preferred_size.height, float(self._pixel_height)),
        )

    def build_scene_node(self) -> SceneNode:
        image_bounds = self._image_bounds()
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=self.clip_to_bounds or self.fit is ImageFit.COVER,
            hit_testable=False,
        )
        root.add(
            SceneNode(
                key=f"{self.key}:image",
                kind=SceneNodeKind.IMAGE,
                bounds=image_bounds,
                resource_id=self.resource_id,
                hit_testable=False,
            )
        )
        return root

    def _image_bounds(self) -> Rect:
        bounds = self.bounds
        if self.fit is ImageFit.FILL:
            return bounds

        source_width = float(self._pixel_width)
        source_height = float(self._pixel_height)
        if self.fit is ImageFit.NONE:
            width = source_width
            height = source_height
        else:
            x_scale = bounds.width / source_width if source_width else 1.0
            y_scale = bounds.height / source_height if source_height else 1.0
            scale = min(x_scale, y_scale) if self.fit is ImageFit.CONTAIN else max(x_scale, y_scale)
            width = source_width * scale
            height = source_height * scale
        return Rect(
            bounds.x + (bounds.width - width) / 2.0,
            bounds.y + (bounds.height - height) / 2.0,
            width,
            height,
        )

    @staticmethod
    def _validate_resource_id(value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("resource_id cannot be empty.")
        return normalized

    @staticmethod
    def _validate_pixel_size(width: int, height: int) -> tuple[int, int]:
        normalized = int(width), int(height)
        if normalized[0] <= 0 or normalized[1] <= 0:
            raise ValueError("pixel_width and pixel_height must be greater than zero.")
        return normalized


__all__ = ["Image", "ImageFit"]
