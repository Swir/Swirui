"""Renderer resource primitives shared by GPU backends."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageResource:
    """Immutable RGBA8 image payload registered with a renderer.

    ``rgba8`` is tightly packed row-major RGBA data with exactly four bytes per
    pixel. File decoding intentionally stays outside the renderer so applications
    can use Pillow, imageio, custom asset pipelines, generated pixels, or embedded
    resources without coupling SwirUI's GPU core to one decoder.
    """

    resource_id: str
    width: int
    height: int
    rgba8: bytes

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("Image resource_id cannot be empty.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Image dimensions must be greater than zero.")
        expected = self.width * self.height * 4
        if len(self.rgba8) != expected:
            raise ValueError(
                f"RGBA8 image requires {expected} bytes for "
                f"{self.width}x{self.height}, received {len(self.rgba8)}."
            )

    @property
    def byte_size(self) -> int:
        return len(self.rgba8)
