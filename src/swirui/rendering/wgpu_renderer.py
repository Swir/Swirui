"""Python-side renderer bridge for the SwirUI Rust/wgpu native core."""

from __future__ import annotations

import importlib
import sys
from typing import Any

from swirui.core import Component, PresentationMode
from swirui.window import Window

from .geometry import Color, Rect
from .scene import SceneNodeKind
from .surface import RenderSurface

ClipRect = tuple[float, float, float, float]
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
    ClipRect,
]
ImageInstance = tuple[str, float, float, float, float, float, ClipRect]
ImageResource = tuple[int, int, bytes]

_DEFAULT_TEXT_COLOR = Color(1.0, 1.0, 1.0, 1.0)


class WgpuRenderer:
    """Submit prepared SwirUI scenes to the native Rust/wgpu renderer.

    Scene geometry is authored in logical device-independent pixels. Before
    crossing the PyO3 boundary it is converted to physical pixels using the
    window's current per-monitor scale, keeping shapes, text, images and clip
    rectangles aligned across mixed-DPI displays.

    Native builds retain one persistent GPU context per window so the expensive
    instance/device/pipeline setup is not repeated for every frame. Images are
    registered once as RGBA resources and uploaded into every active native GPU
    context, while scene nodes only submit lightweight resource references.
    Re-registering byte-identical image content is a cache hit and does not
    recreate textures in active GPU contexts.
    """

    name = "wgpu"

    def __init__(
        self,
        *,
        background: Color | None = None,
        native_module: Any | None = None,
        presentation_mode: PresentationMode = PresentationMode.AUTO_VSYNC,
        maximum_frame_latency: int = 1,
    ) -> None:
        if maximum_frame_latency <= 0:
            raise ValueError("maximum_frame_latency must be positive.")
        self.background = background or Color.from_hex("#070B14")
        self.presentation_mode = presentation_mode
        self.maximum_frame_latency = maximum_frame_latency
        self.initialized = False
        self.frames_rendered = 0
        self.last_rectangle_count = 0
        self.last_text_count = 0
        self.last_image_count = 0
        self.adapter_name: str | None = None
        self.graphics_backend: str | None = None
        self.surfaces: dict[int, RenderSurface] = {}
        self._contexts: dict[int, Any] = {}
        self._image_resources: dict[str, ImageResource] = {}
        self._image_cache_hits = 0
        self._image_native_uploads = 0
        self._native: Any | None = native_module

    @property
    def persistent_context_count(self) -> int:
        return len(self._contexts)

    @property
    def image_resource_count(self) -> int:
        return len(self._image_resources)

    @property
    def image_resource_bytes(self) -> int:
        """Return CPU-side RGBA bytes retained by the persistent image cache."""

        return sum(len(resource[2]) for resource in self._image_resources.values())

    @property
    def image_cache_hits(self) -> int:
        """Return byte-identical image registrations skipped by the cache."""

        return self._image_cache_hits

    @property
    def image_native_uploads(self) -> int:
        """Return actual image uploads issued to persistent native GPU contexts."""

        return self._image_native_uploads

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

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None:
        """Register or replace a cached RGBA8 image used by IMAGE scene nodes.

        Byte-identical re-registration is intentionally a no-op. Changed image
        dimensions or pixels replace the cached resource and are uploaded once
        to each active persistent native context. Future contexts receive only
        the latest cached resource when their surface is created.
        """

        if not resource_id.strip():
            raise ValueError("resource_id cannot be empty.")
        if width <= 0 or height <= 0:
            raise ValueError("Image width and height must be greater than zero.")
        data = bytes(rgba)
        expected = width * height * 4
        if len(data) != expected:
            raise ValueError(
                f"RGBA image resource requires exactly {expected} bytes for "
                f"{width}x{height}; received {len(data)}."
            )

        resource = (width, height, data)
        if self._image_resources.get(resource_id) == resource:
            self._image_cache_hits += 1
            return

        registrations: list[tuple[Any, Any]] = []
        for context in self._contexts.values():
            register = getattr(context, "register_image_rgba", None)
            if register is None:
                raise RuntimeError(
                    "Installed SwirUI native GPU core does not support image resources."
                )
            registrations.append((context, register))

        self._image_resources[resource_id] = resource
        for _context, register in registrations:
            register(resource_id, width, height, data)
            self._image_native_uploads += 1

    def unregister_image(self, resource_id: str) -> bool:
        """Remove an image resource from Python and every active GPU context."""

        removed = self._image_resources.pop(resource_id, None) is not None
        if not removed:
            return False
        for context in self._contexts.values():
            unregister = getattr(context, "unregister_image", None)
            if unregister is not None:
                unregister(resource_id)
        return True

    def create_surface(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("A native window handle is required before creating a GPU surface.")

        handle = window.native_handle.value
        pixel_width, pixel_height = window.pixel_size
        surface = RenderSurface(window.native_handle, pixel_width, pixel_height)
        self.surfaces[handle] = surface

        native = self._native
        context_factory = getattr(native, "Win32GpuRenderer", None) if native is not None else None
        if context_factory is not None:
            if (
                self.presentation_mode is PresentationMode.AUTO_VSYNC
                and self.maximum_frame_latency == 1
            ):
                context = context_factory(handle, pixel_width, pixel_height)
            else:
                context = context_factory(
                    handle,
                    pixel_width,
                    pixel_height,
                    self.presentation_mode.value,
                    self.maximum_frame_latency,
                )
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
            draw_scene = getattr(context, "draw_scene", None)
            if rectangles or texts or images:
                if images and getattr(context, "register_image_rgba", None) is None:
                    raise RuntimeError(
                        "Installed SwirUI native GPU core does not support image rendering."
                    )
                if draw_scene is not None:
                    rectangle_count, text_count, image_count = draw_scene(
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
                elif texts or images:
                    raise RuntimeError(
                        "Installed SwirUI native GPU core does not support the full scene renderer."
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
            self._render_stateless(window, rectangles, texts, images)

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
        images: list[ImageInstance],
    ) -> None:
        native = self._native
        if native is None or window.native_handle is None:
            raise RuntimeError("Native GPU core is unavailable.")
        if images:
            raise RuntimeError(
                "Image rendering requires the persistent SwirUI native GPU context."
            )
        background = self.background
        pixel_width, pixel_height = window.pixel_size
        if texts:
            draw_scene = getattr(native, "draw_scene_win32_surface", None)
            if draw_scene is None:
                raise RuntimeError(
                    "Installed SwirUI native GPU core does not support shaped text rendering."
                )
            adapter_name, graphics_backend, rectangle_count, text_count = draw_scene(
                window.native_handle.value,
                pixel_width,
                pixel_height,
                rectangles,
                texts,
                background.r,
                background.g,
                background.b,
                background.a,
            )
            self.last_rectangle_count = int(rectangle_count)
            self.last_text_count = int(text_count)
            self.last_image_count = 0
        elif rectangles:
            adapter_name, graphics_backend, rectangle_count = (
                native.draw_rectangles_win32_surface(
                    window.native_handle.value,
                    pixel_width,
                    pixel_height,
                    rectangles,
                    background.r,
                    background.g,
                    background.b,
                    background.a,
                )
            )
            self.last_rectangle_count = int(rectangle_count)
            self.last_text_count = 0
            self.last_image_count = 0
        else:
            adapter_name, graphics_backend = native.clear_win32_surface(
                window.native_handle.value,
                pixel_width,
                pixel_height,
                background.r,
                background.g,
                background.b,
                background.a,
            )
            self.last_rectangle_count = 0
            self.last_text_count = 0
            self.last_image_count = 0

        self.adapter_name = str(adapter_name)
        self.graphics_backend = str(graphics_backend)

    def _upload_registered_images(self, context: Any) -> None:
        if not self._image_resources:
            return
        register = getattr(context, "register_image_rgba", None)
        if register is None:
            raise RuntimeError(
                "Installed SwirUI native GPU core does not support image resources."
            )
        for resource_id, (width, height, data) in self._image_resources.items():
            register(resource_id, width, height, data)
            self._image_native_uploads += 1

    def _capture_adapter_info(self, context: Any) -> None:
        self.adapter_name = str(context.adapter_name)
        self.graphics_backend = str(context.graphics_backend)

    @staticmethod
    def _visible_clip(scene_width: float, scene_height: float, clip: Rect | None) -> Rect | None:
        viewport = Rect(0.0, 0.0, scene_width, scene_height)
        return viewport if clip is None else viewport.intersection(clip)

    @staticmethod
    def _scale(value: float, scale: float) -> float:
        return value * scale

    @classmethod
    def _clip_tuple(cls, clip: Rect, scale: float = 1.0) -> ClipRect:
        return (
            cls._scale(clip.x, scale),
            cls._scale(clip.y, scale),
            cls._scale(clip.right, scale),
            cls._scale(clip.bottom, scale),
        )

    def _rectangle_instances(self, window: Window) -> list[RectangleInstance]:
        scene = window.scene
        if scene is None:
            return []

        scale = window.scale
        rectangles: list[RectangleInstance] = []
        for node, effective_opacity, inherited_clip in scene.walk_composited():
            if node.kind not in (SceneNodeKind.GROUP, SceneNodeKind.RECTANGLE):
                continue
            if node.fill is None:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            clip = self._visible_clip(scene.width, scene.height, inherited_clip)
            if clip is None or node.bounds.intersection(clip) is None:
                continue

            fill = node.fill
            radius = node.corner_radius
            clip_left, clip_top, clip_right, clip_bottom = self._clip_tuple(clip, scale)
            rectangles.append(
                (
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    fill.r,
                    fill.g,
                    fill.b,
                    fill.a * effective_opacity,
                    self._scale(radius.top_left, scale),
                    self._scale(radius.top_right, scale),
                    self._scale(radius.bottom_right, scale),
                    self._scale(radius.bottom_left, scale),
                    clip_left,
                    clip_top,
                    clip_right,
                    clip_bottom,
                )
            )
        return rectangles

    def _text_instances(self, window: Window) -> list[TextInstance]:
        scene = window.scene
        if scene is None:
            return []

        scale = window.scale
        texts: list[TextInstance] = []
        for node, effective_opacity, inherited_clip in scene.walk_composited():
            if node.kind is not SceneNodeKind.TEXT:
                continue
            if not node.text:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            clip = self._visible_clip(scene.width, scene.height, inherited_clip)
            if clip is None or node.bounds.intersection(clip) is None:
                continue

            fill = node.fill or _DEFAULT_TEXT_COLOR
            texts.append(
                (
                    node.text,
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    self._scale(node.font_size, scale),
                    fill.r,
                    fill.g,
                    fill.b,
                    fill.a * effective_opacity,
                    node.font_family,
                    self._clip_tuple(clip, scale),
                )
            )
        return texts

    def _image_instances(self, window: Window) -> list[ImageInstance]:
        scene = window.scene
        if scene is None:
            return []

        scale = window.scale
        images: list[ImageInstance] = []
        for node, effective_opacity, inherited_clip in scene.walk_composited():
            if node.kind is not SceneNodeKind.IMAGE:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            clip = self._visible_clip(scene.width, scene.height, inherited_clip)
            if clip is None or node.bounds.intersection(clip) is None:
                continue
            resource_id = node.resource_id
            if resource_id is None or resource_id not in self._image_resources:
                raise RuntimeError(
                    f"Scene image resource {resource_id!r} is not registered with WgpuRenderer."
                )
            images.append(
                (
                    resource_id,
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    effective_opacity,
                    self._clip_tuple(clip, scale),
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
