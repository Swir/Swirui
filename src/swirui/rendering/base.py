"""Renderer contracts used by SwirUI."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from swirui.core import Component
from swirui.window import Window

from .surface import RenderSurface


@runtime_checkable
class Renderer(Protocol):
    """Backend contract for turning component trees into presented frames.

    Surface dimensions are physical pixels. Window and scene geometry remain
    logical device-independent pixels at the public framework boundary.
    """

    @property
    def name(self) -> str: ...

    def initialize(self) -> None: ...

    def create_surface(self, window: Window) -> RenderSurface: ...

    def resize_surface(self, window: Window, width: int, height: int) -> None: ...

    def destroy_surface(self, window: Window) -> None: ...

    def render(self, window: Window, root: Component | None) -> None: ...

    def shutdown(self) -> None: ...


class NullRenderer:
    """Headless renderer that validates the same lifecycle as GPU backends."""

    name = "null"

    def __init__(self) -> None:
        self.initialized = False
        self.frames_rendered = 0
        self.surfaces: dict[int, RenderSurface] = {}

    def initialize(self) -> None:
        self.initialized = True

    def create_surface(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("A native window handle is required before creating a surface.")
        pixel_width, pixel_height = window.pixel_size
        surface = RenderSurface(window.native_handle, pixel_width, pixel_height)
        self.surfaces[window.native_handle.value] = surface
        return surface

    def resize_surface(self, window: Window, width: int, height: int) -> None:
        surface = self._surface_for(window)
        surface.resize(width, height)

    def destroy_surface(self, window: Window) -> None:
        if window.native_handle is None:
            return
        surface = self.surfaces.pop(window.native_handle.value, None)
        if surface is not None:
            surface.destroy()

    def render(self, window: Window, root: Component | None) -> None:
        self._require_initialized()
        del window, root
        self.frames_rendered += 1

    def shutdown(self) -> None:
        for surface in self.surfaces.values():
            surface.destroy()
        self.surfaces.clear()
        self.initialized = False

    def _surface_for(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        try:
            return self.surfaces[window.native_handle.value]
        except KeyError as exc:
            raise RuntimeError("Window does not have an attached render surface.") from exc

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("Renderer must be initialized before use.")
