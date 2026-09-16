"""Python-side renderer bridge for the SwirUI Rust/wgpu native core."""

from __future__ import annotations

import importlib
import sys
from typing import Any

from swirui.core import Component
from swirui.window import Window

from .geometry import Color
from .resources import ImageResource
from .scene import SceneNodeKind
from .surface import RenderSurface

RectangleInstance = tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
]
TextInstance = tuple[
    str,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    str,
]
ImageInstance = tuple[str, float, float, float, float, float]

_DEFAULT_TEXT_COLOR = Color(1.0, 1.0, 1.0, 1.0)


class WgpuRenderer:
    """Submit prepared SwirUI scenes to the native Rust/wgpu renderer.

    Native builds retain one persistent GPU context per window so the expensive
    instance/device/pipeline setup is not repeated for every frame. Image pixels
    are uploaded once per resource registration and then reused from the native
    GPU cache until replaced or explicitly removed.
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
        self.last_text_count = 0
        self.last_image_count = 0
        self.adapter_name: str | None = None
        self.graphics_backend: str | None = None
        self.surfaces: dict[int, RenderSurface] = {}
        self._contexts: dict[int, Any] = {}
        self._images: dict[str, ImageResource] = {}
        self._native: Any | None = native_module

    @property
    def persistent_context_count(self) -> int:
        return len(self._contexts)

    @property
    def image_resource_count(self) -> int:
        return len(self._images)

    def register_image(self, resource: ImageResource) -> None:
        """Register or replace an immutable RGBA8 image resource.

        Existing native contexts receive the upload immediately. Contexts created
        later replay the Python registry, so multi-window rendering shares one
        stable public resource id without requiring application-side reuploads.
        """

        self._images[resource.resource_id] = resource
        for context in self._contexts.values():
            register = getattr(context, "register_image_rgba8", None)
            if register is None:
                raise RuntimeError(
                    "Installed SwirUI native GPU core does not support image resources."
                )
            register(resource.resource_id, resource.width, resource.height, resource.rgba8)

    def register_image_rgba8(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba8: bytes,
    ) -> ImageResource:
        """Create and register a tightly packed RGBA8 image resource."""

        resource = ImageResource(resource_id, width, height, rgba8)
        self.register_image(resource)
        return resource

    def unregister_image(self, resource_id: str) -> bool:
        """Remove an image from Python and all currently alive native contexts."""

        removed = self._images.pop(resource_id, None) is not None
        native_removed = False
        for context in self._contexts.values():
            unregister = getattr(context, "unregister_image", None)
            if unregister is not None:
                native_removed = bool(unregister(resource_id)) or native_removed
        return removed or native_removed

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

        handle = window.native_handle.value
        surface = RenderSurface(window.native_handle, window.width, window.height)
        self.surfaces[handle] = surface

        native = self._native
        context_factory = getattr(native, "Win32GpuRenderer", None) if native is not None else None
        if context_factory is not None:
            context = context_factory(handle, window.width, window.height)
            self._contexts[handle] = context
            self._upload_registered_images(context)
            self._capture_adapter_info(context)
        return surface

    def resize_surface(self, window: Window, width: int, height: int) -> None:
        self._surface_for(window).resize(width, height)
        if window.native_handle is None:
            return
        context = self._contexts.get(window.native_handle.value)
        if context is not None:
            context.resize(width, height)

    def destroy_surface(self, window: Window) -> None:
        if window.native_handle is None:
            return
        handle = window.native_handle.value
        self._contexts.pop(handle, None)
        surface = self.surfaces.pop(handle, None)
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
        texts = self._text_instances(window)
        images = self._image_instances(window)
        background = self.background
        context = self._contexts.get(window.native_handle.value)
        if context is not None:
            if images:
                draw_scene_images = getattr(context, "draw_scene_images", None)
                if draw_scene_images is None:
                    raise RuntimeError(
                        "Installed SwirUI native GPU core does not support image rendering."
                    )
                rectangle_count, text_count, image_count = draw_scene_images(
                    rectangles,
                    texts,
                    images,
                    background.r,
                    background.g,
                    background.b,
                    background.a,
                )
                self.last_rectangle_count = int(rectangle_count)
                self.last_text_count = int(text_count)
                self.last_image_count = int(image_count)
            elif rectangles or texts:
                draw_scene = getattr(context, "draw_scene", None)
                if draw_scene is not None:
                    rectangle_count, text_count = draw_scene(
                        rectangles,
                        texts,
                        background.r,
                        background.g,
                        background.b,
                        background.a,
                    )
                    self.last_rectangle_count = int(rectangle_count)
                    self.last_text_count = int(text_count)
                elif texts:
                    raise RuntimeError(
                        "Installed SwirUI native GPU core does not support shaped text rendering."
                    )
                else:
                    self.last_rectangle_count = int(
                        context.draw_rectangles(
                            rectangles,
                            background.r,
                            background.g,
                            background.b,
                            background.a,
                        )
                    )
                    self.last_text_count = 0
                self.last_image_count = 0
            else:
                context.clear(background.r, background.g, background.b, background.a)
                self.last_rectangle_count = 0
                self.last_text_count = 0
                self.last_image_count = 0
            self._capture_adapter_info(context)
        else:
            if images:
                raise RuntimeError(
                    "Image rendering requires the persistent native Win32 GPU context."
                )
            self._render_stateless(window, rectangles, texts)
            self.last_image_count = 0

        self.frames_rendered += 1

    def shutdown(self) -> None:
        self._contexts.clear()
        for surface in self.surfaces.values():
            surface.destroy()
        self.surfaces.clear()
        self.initialized = False

    def _render_stateless(
        self,
        window: Window,
        rectangles: list[RectangleInstance],
        texts: list[TextInstance],
    ) -> None:
        native = self._native
        if native is None or window.native_handle is None:
            raise RuntimeError("Native GPU core is unavailable.")
        background = self.background
        if texts:
            draw_scene = getattr(native, "draw_scene_win32_surface", None)
            if draw_scene is None:
                raise RuntimeError(
                    "Installed SwirUI native GPU core does not support shaped text rendering."
                )
            adapter_name, graphics_backend, rectangle_count, text_count = draw_scene(
                window.native_handle.value,
                window.width,
                window.height,
                rectangles,
                texts,
                background.r,
                background.g,
                background.b,
                background.a,
            )
            self.last_rectangle_count = int(rectangle_count)
            self.last_text_count = int(text_count)
        elif rectangles:
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
            self.last_text_count = 0
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
            self.last_text_count = 0

        self.adapter_name = str(adapter_name)
        self.graphics_backend = str(graphics_backend)

    def _upload_registered_images(self, context: Any) -> None:
        if not self._images:
            return
        register = getattr(context, "register_image_rgba8", None)
        if register is None:
            raise RuntimeError(
                "Installed SwirUI native GPU core does not support image resources."
            )
        for resource in self._images.values():
            register(resource.resource_id, resource.width, resource.height, resource.rgba8)

    def _capture_adapter_info(self, context: Any) -> None:
        self.adapter_name = str(context.adapter_name)
        self.graphics_backend = str(context.graphics_backend)

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
            radius = node.corner_radius
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
                    radius.top_left,
                    radius.top_right,
                    radius.bottom_right,
                    radius.bottom_left,
                )
            )
        return rectangles

    def _text_instances(self, window: Window) -> list[TextInstance]:
        scene = window.scene
        if scene is None:
            return []

        texts: list[TextInstance] = []
        for node in scene.walk():
            if node.kind is not SceneNodeKind.TEXT:
                continue
            if not node.text or node.opacity <= 0.0:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue

            fill = node.fill or _DEFAULT_TEXT_COLOR
            texts.append(
                (
                    node.text,
                    node.bounds.x,
                    node.bounds.y,
                    node.bounds.width,
                    node.bounds.height,
                    node.font_size,
                    fill.r,
                    fill.g,
                    fill.b,
                    fill.a * node.opacity,
                    node.font_family,
                )
            )
        return texts

    def _image_instances(self, window: Window) -> list[ImageInstance]:
        scene = window.scene
        if scene is None:
            return []

        images: list[ImageInstance] = []
        for node in scene.walk():
            if node.kind is not SceneNodeKind.IMAGE:
                continue
            if node.opacity <= 0.0:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            resource_id = node.resource_id
            if resource_id is None or resource_id not in self._images:
                raise RuntimeError(
                    f"Scene image node {node.key!r} references an unregistered resource "
                    f"{resource_id!r}."
                )
            images.append(
                (
                    resource_id,
                    node.bounds.x,
                    node.bounds.y,
                    node.bounds.width,
                    node.bounds.height,
                    node.opacity,
                )
            )
        return images

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
