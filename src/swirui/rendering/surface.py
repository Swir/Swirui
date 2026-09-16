"""Backend-neutral render-surface lifecycle for SwirUI."""

from __future__ import annotations

from dataclasses import dataclass

from swirui.platforms import NativeWindowHandle


@dataclass(slots=True)
class RenderSurface:
    """Logical presentation surface associated with one native window."""

    window_handle: NativeWindowHandle
    width: int
    height: int
    scale: float = 1.0
    generation: int = 0
    alive: bool = True

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Render surface dimensions must be positive.")
        if self.scale <= 0:
            raise ValueError("Render surface scale must be positive.")

    def resize(self, width: int, height: int, *, scale: float | None = None) -> bool:
        if width <= 0 or height <= 0:
            raise ValueError("Render surface dimensions must be positive.")
        new_scale = self.scale if scale is None else scale
        if new_scale <= 0:
            raise ValueError("Render surface scale must be positive.")
        if (width, height, new_scale) == (self.width, self.height, self.scale):
            return False
        self.width = width
        self.height = height
        self.scale = new_scale
        self.generation += 1
        return True

    def destroy(self) -> None:
        if self.alive:
            self.alive = False
            self.generation += 1
