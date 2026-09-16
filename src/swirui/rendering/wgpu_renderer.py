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
PathTriangleInstance = tuple[float, ...]
ImageResource = tuple[int, int, bytes]

_DEFAULT_TEXT_COLOR = Color(1.0, 1.0, 1.0, 1.0)


class WgpuRenderer:
    """Submit prepared SwirUI scenes to the native Rust/wgpu renderer.

    Scene geometry is authored in logical device-independent pixels. Before
    crossing the PyO3 boundary it is converted to physical pixels using the
    window's current per-monitor scale, keeping shapes, text, images, paths and
    clip rectangles aligned across mixed-DPI displays.

    Native builds retain one persistent GPU context per window so the expensive
    instance/device/pipeline setup is not repeated for every frame. Image
    registrations are content-addressed: byte-identical RGBA resources share a
    single native texture even when applications expose them under different
    logical resource ids. Logical ids are rebound transactionally while native
    textures stay alive until their final alias is released.
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
        self.last_path_count = 0
        self.adapter_name: str | None = None
        self.graphics_backend: str | None = None
        self.surfaces: dict[int, RenderSurface] = {}
        self._contexts: dict[int, Any] = {}
        self._image_resources: dict[str, ImageResource] = {}
        self._image_aliases: dict[str, str] = {}
        self._image_content_index: dict[ImageResource, str] = {}
        self._image_cache_hits = 0
        self._image_native_uploads = 0
        self._native: Any | None = native_module

    @property
    def persistent_context_count(self) -> int:
        return len(self._contexts)

    @property
    def image_resource_count(self) -> int:
        """Return the number of logical image ids registered by the application."""

        return len(self._image_aliases)

    @property
    def image_gpu_resource_count(self) -> int:
        """Return the number of unique RGBA payloads retained for native upload."""

        return len(self._image_resources)

    @property
    def image_alias_count(self) -> int:
        """Return logical image ids currently sharing an existing GPU resource."""

        return self.image_resource_count - self.image_gpu_resource_count

    @property
    def image_resource_bytes(self) -> int:
        """Return unique CPU-side RGBA bytes retained by the persistent cache."""

        return sum(len(resource[2]) for resource in self._image_resources.values())

    @property
    def image_cache_hits(self) -> int:
        """Return same-id and cross-id registrations served by the image cache."""

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
        """Register or replace an RGBA8 image used by IMAGE scene nodes.

        Byte-identical content is cached globally inside this renderer. A second
        logical resource id that references identical dimensions and RGBA bytes
        becomes an alias of the already-uploaded native texture instead of
        allocating another GPU resource. Rebinding one alias to different pixels
        leaves the old texture alive while other aliases still reference it.
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
        previous_native_id = self._image_aliases.get(resource_id)
        if previous_native_id is not None:
            previous_resource = self._image_resources[previous_native_id]
            if previous_resource == resource:
                self._image_cache_hits += 1
                return

        cached_native_id = self._image_content_index.get(resource)
        if cached_native_id is not None:
            self._image_aliases[resource_id] = cached_native_id
            self._image_cache_hits += 1
            if previous_native_id is not None and previous_native_id != cached_native_id:
                self._release_native_image_if_unused(previous_native_id)
            return

        native_id = self._allocate_native_image_id(resource_id)
        registrations: list[tuple[Any, Any]] = []
        for context in self._contexts.values():
            register = getattr(context, "register_image_rgba", None)
            if register is None:
                raise RuntimeError(
                    "Installed SwirUI native GPU core does not support image resources."
                )
            registrations.append((context, register))

        uploaded_contexts: list[Any] = []
        try:
            for context, register in registrations:
                register(native_id, width, height, data)
                uploaded_contexts.append(context)
        except Exception:
            for context in uploaded_contexts:
                unregister = getattr(context, "unregister_image", None)
                if unregister is not None:
                    unregister(native_id)
            raise

        self._image_resources[native_id] = resource
        self._image_content_index[resource] = native_id
        self._image_aliases[resource_id] = native_id
        self._image_native_uploads += len(uploaded_contexts)
        if previous_native_id is not None and previous_native_id != native_id:
            self._release_native_image_if_unused(previous_native_id)

    def unregister_image(self, resource_id: str) -> bool:
        """Remove one logical image id and release its GPU texture when unreferenced."""

        native_id = self._image_aliases.pop(resource_id, None)
        if native_id is None:
            return False
        self._release_native_image_if_unused(native_id)
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
        paths = self._path_instances(window)
        background = self.background
        context = self._contexts.get(window.native_handle.value)
        if context is not None:
            draw_scene = getattr(context, "draw_scene", None)
            if rectangles or texts or images or paths:
                if images and getattr(context, "register_image_rgba", None) is None:
                    raise RuntimeError(
                        "Installed SwirUI native GPU core does not support image rendering."
                    )
                if paths:
                    draw_scene_with_paths = getattr(context, "draw_scene_with_paths", None)
                    if draw_scene_with_paths is None:
                        raise RuntimeError(
                            "Installed SwirUI native GPU core does not support path rendering."
                        )
                    rectangle_count, text_count, image_count, path_count = draw_scene_with_paths(
                        rectangles,
                        texts,
                        images,
                        paths,
                        background.r,
                        background.g,
                        background.b,
                        background.a,
                    )
                    self.last_rectangle_count = int(rectangle_count)
                    self.last_text_count = int(text_count)
                    self.last_image_count = int(image_count)
                    self.last_path_count = int(path_count)
                elif draw_scene is not None:
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
                    self.last_path_count = 0
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
                    self.last_path_count = 0
            else:
                context.clear(background.r, background.g, background.b, background.a)
                self.last_rectangle_count = 0
                self.last_text_count = 0
                self.last_image_count = 0
                self.last_path_count = 0
            self._capture_adapter_info(context)
        else:
            self._render_stateless(window, rectangles, texts, images, paths)

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
        paths: list[PathTriangleInstance],
    ) -> None:
        native = self._native
        if native is None or window.native_handle is None:
            raise RuntimeError("Native GPU core is unavailable.")
        if images:
            raise RuntimeError(
                "Image rendering requires the persistent SwirUI native GPU context."
            )
        if paths:
            raise RuntimeError(
                "Path rendering requires the persistent SwirUI native GPU context."
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
            self.last_path_count = 0
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
            self.last_path_count = 0
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
            self.last_path_count = 0

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
        for native_id, (width, height, data) in self._image_resources.items():
            register(native_id, width, height, data)
            self._image_native_uploads += 1

    def _allocate_native_image_id(self, preferred: str) -> str:
        if preferred not in self._image_resources:
            return preferred
        suffix = 1
        while f"{preferred}#{suffix}" in self._image_resources:
            suffix += 1
        return f"{preferred}#{suffix}"

    def _release_native_image_if_unused(self, native_id: str) -> None:
        if native_id in self._image_aliases.values():
            return
        resource = self._image_resources.pop(native_id, None)
        if resource is None:
            return
        self._image_content_index.pop(resource, None)
        for context in self._contexts.values():
            unregister = getattr(context, "unregister_image", None)
            if unregister is not None:
                unregister(native_id)

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
            native_id = self._image_aliases.get(resource_id) if resource_id is not None else None
            if native_id is None:
                raise RuntimeError(
                    f"Scene image resource {resource_id!r} is not registered with WgpuRenderer."
                )
            images.append(
                (
                    native_id,
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    effective_opacity,
                    self._clip_tuple(clip, scale),
                )
            )
        return images

    def _path_instances(self, window: Window) -> list[PathTriangleInstance]:
        scene = window.scene
        if scene is None:
            return []

        scale = window.scale
        paths: list[PathTriangleInstance] = []
        for node, effective_opacity, inherited_clip in scene.walk_composited():
            if node.kind is not SceneNodeKind.PATH or node.path is None or node.fill is None:
                continue
            clip = self._visible_clip(scene.width, scene.height, inherited_clip)
            if clip is None or node.path.bounds.intersection(clip) is None:
                continue
            fill = node.fill
            clip_tuple = self._clip_tuple(clip, scale)
            for triangle in node.path.triangles():
                paths.append(
                    (
                        self._scale(triangle.a.x, scale),
                        self._scale(triangle.a.y, scale),
                        self._scale(triangle.b.x, scale),
                        self._scale(triangle.b.y, scale),
                        self._scale(triangle.c.x, scale),
                        self._scale(triangle.c.y, scale),
                        fill.r,
                        fill.g,
                        fill.b,
                        fill.a * effective_opacity,
                        *clip_tuple,
                    )
                )
        return paths

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
