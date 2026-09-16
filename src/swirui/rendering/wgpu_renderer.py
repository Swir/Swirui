"""Python-side renderer bridge for the SwirUI Rust/wgpu native core."""

from __future__ import annotations

import importlib
import sys
from typing import Any

from swirui.core import Component
from swirui.window import Window

from .geometry import Color
from .scene import SceneNodeKind
from .surface import RenderSurface

RectangleInstance = tuple[float, float, float, float, float, float, float, float]


class WgpuRenderer:
    """Submit prepared SwirUI scenes to the native Rust/wgpu renderer.

    The first implementation intentionally supports filled rectangles only. Text,
    images, clipping and rounded corners are added progressively without changing
    the framework-level renderer contract.
    """

    name = "wgpu"

    def __init__(
        self,
        *,
        background: Color | None = None,
        native_module: Any | None = None,
    ) -> None:
        self.background = background or Color.from_hex("#070B14")
        self.initialized = False
        self.frames_rendered = 0
        self.last_rectangle_count = 0
        self.adapter_name: str | None = None
        self.graphics_backend: str | None = None
        self.surfaces: dict[int, RenderSurface] = {}
        self._native: Any | None = native_module

    def initialize(self) -> None:
        if self.initialized:
            return
        if self._native is None:
            if sys.platform != "win32":
                raise RuntimeError("The first SwirUI wgpu bridge currently requires Windows.")
            try:
                self._native = importlib.import_module("_swirui_native")
            except ImportError as exc:
                raise RuntimeError(
                    "SwirUI native GPU core is not installed. Build/install native/ with Maturin."
                ) from exc
        self.initialized = True

    def create_surface(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("A native window handle is required before creating a GPU surface.")
        surface = RenderSurface(window.native_handle, window.width, window.height)
        self.surfaces[window.native_handle.value] = surface
        return surface

    def resize_surface(self, window: Window, width: int, height: int) -> None:
        self._surface_for(window).resize(width, height)

    def destroy_surface(self, window: Window) -> None:
        if window.native_handle is None:
            return
        surface = self.surfaces.pop(window.native_handle.value, None)
        if surface is not None:
            surface.destroy()

    def render(self, window: Window, root: Component | None) -> None:
        del root
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        self._surface_for(window)
        native = self._native
        if native is None:
            raise RuntimeError("Native GPU core is unavailable.")

        rectangles = self._rectangle_instances(window)
        background = self.background
        if rectangles:
            adapter_name, graphics_backend, rectangle_count = (
                native.draw_rectangles_win32_surface(
                    window.native_handle.value,
                    window.width,
                    window.height,
                    rectangles,
                    background.r,
                    background.g,
                    background.b,
                    background.a,
                )
            )
            self.last_rectangle_count = int(rectangle_count)
        else:
            adapter_name, graphics_backend = native.clear_win32_surface(
                window.native_handle.value,
                window.width,
                window.height,
                background.r,
                background.g,
                background.b,
                background.a,
            )
            self.last_rectangle_count = 0

        self.adapter_name = str(adapter_name)
        self.graphics_backend = str(graphics_backend)
        self.frames_rendered += 1

    def shutdown(self) -> None:
        for surface in self.surfaces.values():
            surface.destroy()
        self.surfaces.clear()
        self.initialized = False

    def _rectangle_instances(self, window: Window) -> list[RectangleInstance]:
        scene = window.scene
        if scene is None:
            return []

        rectangles: list[RectangleInstance] = []
        for node in scene.walk():
            if node.kind not in (SceneNodeKind.GROUP, SceneNodeKind.RECTANGLE):
                continue
            if node.fill is None or node.opacity <= 0.0:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue

            fill = node.fill
            rectangles.append(
                (
                    node.bounds.x,
                    node.bounds.y,
                    node.bounds.width,
                    node.bounds.height,
                    fill.r,
                    fill.g,
                    fill.b,
                    fill.a * node.opacity,
                )
            )
        return rectangles

    def _surface_for(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        try:
            return self.surfaces[window.native_handle.value]
        except KeyError as exc:
            raise RuntimeError("Window does not have an attached GPU surface.") from exc

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("Renderer must be initialized before use.")
