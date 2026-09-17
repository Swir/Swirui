"""Backdrop-aware extension of the persistent Rust/wgpu renderer bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from swirui.core import Component, PresentationMode
from swirui.window import Window

from .color_filters import ColorFilter
from .geometry import Color, Rect
from .scene import Scene, SceneNode, SceneNodeKind
from .surface import RenderSurface
from .wgpu_renderer import ImageInstance, RectangleInstance, ShapeVertex, TextInstance
from .wgpu_renderer import WgpuRenderer as _BaseWgpuRenderer

BackdropRegion = tuple[float, float, float, float, float, float, float, float, float]
BackdropPayload = tuple[
    list[list[RectangleInstance]],
    list[list[TextInstance]],
    list[list[ImageInstance]],
    list[list[ShapeVertex]],
    list[BackdropRegion],
]

_DEFAULT_TEXT_COLOR = Color(1.0, 1.0, 1.0, 1.0)


@dataclass(slots=True)
class _BackdropPayloadCacheEntry:
    scene: Scene
    generation: int
    scale: float
    image_aliases: tuple[tuple[str, str], ...]
    payload: BackdropPayload | None


class WgpuRenderer(_BaseWgpuRenderer):
    """Persistent GPU renderer with backdrop blur and final color filtering.

    Backdrop nodes split a retained scene into ordered segments. Each segment is
    submitted into the same persistent offscreen target, the already-painted
    backdrop is blurred and composited into the requested rounded region, and
    later segments are then drawn sharp on top. Scenes without backdrop nodes
    stay on the existing fast path without extra segmentation or GPU passes.

    Prepared backdrop payloads are cached once per window. Re-rendering an
    unchanged retained ``Scene`` therefore reuses the already-scaled rectangle,
    text, image and tessellated path segments instead of rebuilding them on every
    high-refresh frame. ``Scene.touch()`` is the explicit invalidation boundary
    for in-place scene mutations; replacing the scene, changing DPI scale or
    rebinding image aliases also invalidates the prepared payload automatically.

    ``color_filter`` is an optional affine RGBA transform applied by one retained
    native post-process pass after scene blur/backdrop composition and before the
    swapchain blit. Changing the filter only updates a uniform buffer; it does not
    rebuild the wgpu pipeline or recreate its full-size output target.
    """

    def __init__(
        self,
        *,
        background: Color | None = None,
        native_module: Any | None = None,
        presentation_mode: PresentationMode = PresentationMode.AUTO_VSYNC,
        maximum_frame_latency: int = 1,
        scene_blur_radius: float = 0.0,
        color_filter: ColorFilter | None = None,
    ) -> None:
        super().__init__(
            background=background,
            native_module=native_module,
            presentation_mode=presentation_mode,
            maximum_frame_latency=maximum_frame_latency,
            scene_blur_radius=scene_blur_radius,
        )
        self.color_filter = color_filter
        self.last_backdrop_count = 0
        self._backdrop_payload_cache: dict[int, _BackdropPayloadCacheEntry] = {}
        self._backdrop_payload_cache_hits = 0
        self._backdrop_payload_cache_misses = 0

    @property
    def backdrop_payload_cache_hits(self) -> int:
        """Return prepared backdrop payload requests served without rebuilding."""

        return self._backdrop_payload_cache_hits

    @property
    def backdrop_payload_cache_misses(self) -> int:
        """Return prepared backdrop payload requests that required rebuilding."""

        return self._backdrop_payload_cache_misses

    @property
    def backdrop_payload_cache_entries(self) -> int:
        """Return the number of retained per-window prepared payload entries."""

        return len(self._backdrop_payload_cache)

    def clear_backdrop_payload_cache(self, window: Window | None = None) -> None:
        """Drop prepared backdrop payloads globally or for one window.

        Applications normally do not need this method: replacing ``Window.scene``
        or calling ``Scene.touch()`` after an in-place mutation invalidates the
        cached payload automatically. This hook is useful for diagnostics and
        explicit resource-pressure handling.
        """

        if window is None:
            self._backdrop_payload_cache.clear()
            return
        self._backdrop_payload_cache.pop(self._backdrop_cache_key(window), None)

    def reset_backdrop_payload_cache_stats(self) -> None:
        """Reset hit/miss telemetry without discarding retained payloads."""

        self._backdrop_payload_cache_hits = 0
        self._backdrop_payload_cache_misses = 0

    def set_color_filter(self, color_filter: ColorFilter | None) -> None:
        """Update the final GPU color transform for current and future windows."""

        self.color_filter = color_filter
        for context in self._contexts.values():
            self._configure_color_filter(context)

    def create_surface(self, window: Window) -> RenderSurface:
        surface = super().create_surface(window)
        if window.native_handle is not None:
            context = self._contexts.get(window.native_handle.value)
            if context is not None:
                self._configure_color_filter(context)
        return surface

    def destroy_surface(self, window: Window) -> None:
        self.clear_backdrop_payload_cache(window)
        super().destroy_surface(window)

    def shutdown(self) -> None:
        self._backdrop_payload_cache.clear()
        super().shutdown()

    def render(self, window: Window, root: Component | None) -> None:
        payload = self._backdrop_payload(window)
        if payload is None:
            if (
                self.color_filter is not None
                and window.native_handle is not None
                and window.native_handle.value not in self._contexts
            ):
                raise RuntimeError(
                    "Color filters require the persistent SwirUI native GPU context."
                )
            self.last_backdrop_count = 0
            super().render(window, root)
            return

        del root
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        self._surface_for(window)
        handle = window.native_handle.value
        context = self._contexts.get(handle)
        if context is None:
            raise RuntimeError(
                "Backdrop blur requires the persistent SwirUI native GPU context."
            )
        draw = getattr(context, "draw_scene_with_backdrops", None)
        if draw is None:
            raise RuntimeError(
                "Installed SwirUI native GPU core does not support backdrop blur."
            )

        self._context_scales[handle] = window.scale
        self._configure_scene_blur(context, window.scale)
        rectangles, texts, images, paths, backdrops = payload
        background = self.background
        counts = draw(
            rectangles,
            texts,
            images,
            paths,
            backdrops,
            background.r,
            background.g,
            background.b,
            background.a,
        )
        (
            rectangle_count,
            text_count,
            image_count,
            path_count,
            backdrop_count,
        ) = counts
        self.last_rectangle_count = int(rectangle_count)
        self.last_text_count = int(text_count)
        self.last_image_count = int(image_count)
        self.last_path_count = int(path_count)
        self.last_backdrop_count = int(backdrop_count)
        self._capture_adapter_info(context)
        self.frames_rendered += 1

    def _configure_color_filter(self, context: Any) -> None:
        if self.color_filter is None:
            clear = getattr(context, "clear_color_filter", None)
            if clear is not None:
                clear()
            return
        configure = getattr(context, "set_color_filter", None)
        if configure is None:
            raise RuntimeError(
                "Installed SwirUI native GPU core does not support color filters."
            )
        configure(list(self.color_filter.native_values()))

    def _backdrop_payload(self, window: Window) -> BackdropPayload | None:
        scene = window.scene
        if scene is None:
            return None

        cache_key = self._backdrop_cache_key(window)
        image_aliases = tuple(sorted(self._image_aliases.items()))
        cached = self._backdrop_payload_cache.get(cache_key)
        if (
            cached is not None
            and cached.scene is scene
            and cached.generation == scene.generation
            and cached.scale == window.scale
            and cached.image_aliases == image_aliases
        ):
            self._backdrop_payload_cache_hits += 1
            return cached.payload

        self._backdrop_payload_cache_misses += 1
        records = list(scene.walk_composited())
        if not any(node.kind is SceneNodeKind.BACKDROP_BLUR for node, _, _ in records):
            self._backdrop_payload_cache[cache_key] = _BackdropPayloadCacheEntry(
                scene=scene,
                generation=scene.generation,
                scale=window.scale,
                image_aliases=image_aliases,
                payload=None,
            )
            return None

        rectangle_segments: list[list[RectangleInstance]] = [[]]
        text_segments: list[list[TextInstance]] = [[]]
        image_segments: list[list[ImageInstance]] = [[]]
        path_segments: list[list[ShapeVertex]] = [[]]
        backdrops: list[BackdropRegion] = []
        scale = window.scale

        for node, effective_opacity, inherited_clip in records:
            if node.kind is SceneNodeKind.BACKDROP_BLUR:
                viewport_clip = self._visible_clip(scene.width, scene.height, inherited_clip)
                if viewport_clip is None:
                    continue
                visible = node.bounds.intersection(viewport_clip)
                if visible is None:
                    continue
                backdrops.append(self._backdrop_region(node, visible, scale))
                rectangle_segments.append([])
                text_segments.append([])
                image_segments.append([])
                path_segments.append([])
                continue

            self._append_node(
                node,
                effective_opacity,
                inherited_clip,
                scene.width,
                scene.height,
                scale,
                rectangle_segments[-1],
                text_segments[-1],
                image_segments[-1],
                path_segments[-1],
            )

        payload: BackdropPayload | None
        if not backdrops:
            payload = None
        else:
            payload = (
                rectangle_segments,
                text_segments,
                image_segments,
                path_segments,
                backdrops,
            )
        self._backdrop_payload_cache[cache_key] = _BackdropPayloadCacheEntry(
            scene=scene,
            generation=scene.generation,
            scale=window.scale,
            image_aliases=image_aliases,
            payload=payload,
        )
        return payload

    @staticmethod
    def _backdrop_cache_key(window: Window) -> int:
        if window.native_handle is not None:
            return window.native_handle.value
        return id(window)

    def _append_node(
        self,
        node: SceneNode,
        effective_opacity: float,
        inherited_clip: Rect | None,
        scene_width: float,
        scene_height: float,
        scale: float,
        rectangles: list[RectangleInstance],
        texts: list[TextInstance],
        images: list[ImageInstance],
        paths: list[ShapeVertex],
    ) -> None:
        clip = self._visible_clip(scene_width, scene_height, inherited_clip)
        if clip is None or node.bounds.intersection(clip) is None:
            return

        if node.kind in (SceneNodeKind.GROUP, SceneNodeKind.RECTANGLE):
            if node.fill is None or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                return
            rectangle_fill = node.fill
            radius = node.corner_radius
            clip_left, clip_top, clip_right, clip_bottom = self._clip_tuple(clip, scale)
            rectangles.append(
                (
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    rectangle_fill.r,
                    rectangle_fill.g,
                    rectangle_fill.b,
                    rectangle_fill.a * effective_opacity,
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
            return

        if node.kind is SceneNodeKind.TEXT:
            if not node.text or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                return
            text_fill = node.fill or _DEFAULT_TEXT_COLOR
            texts.append(
                (
                    node.text,
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    self._scale(node.font_size, scale),
                    text_fill.r,
                    text_fill.g,
                    text_fill.b,
                    text_fill.a * effective_opacity,
                    node.font_family,
                    self._clip_tuple(clip, scale),
                )
            )
            return

        if node.kind is SceneNodeKind.IMAGE:
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                return
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
            return

        if node.kind is SceneNodeKind.PATH:
            path = node.path
            path_fill = node.fill
            if (
                path is None
                or path_fill is None
                or node.bounds.width <= 0.0
                or node.bounds.height <= 0.0
            ):
                return
            clip_left, clip_top, clip_right, clip_bottom = self._clip_tuple(clip, scale)
            alpha = path_fill.a * effective_opacity
            for triangle in path.triangulate():
                for point in triangle:
                    paths.append(
                        (
                            self._scale(node.bounds.x + point.x, scale),
                            self._scale(node.bounds.y + point.y, scale),
                            path_fill.r,
                            path_fill.g,
                            path_fill.b,
                            alpha,
                            clip_left,
                            clip_top,
                            clip_right,
                            clip_bottom,
                        )
                    )

    @classmethod
    def _backdrop_region(cls, node: SceneNode, visible: Rect, scale: float) -> BackdropRegion:
        radius = node.corner_radius
        bounds = node.bounds
        left_intact = visible.x == bounds.x
        top_intact = visible.y == bounds.y
        right_intact = visible.right == bounds.right
        bottom_intact = visible.bottom == bounds.bottom
        return (
            cls._scale(visible.x, scale),
            cls._scale(visible.y, scale),
            cls._scale(visible.width, scale),
            cls._scale(visible.height, scale),
            cls._scale(node.blur_radius, scale),
            cls._scale(radius.top_left if left_intact and top_intact else 0.0, scale),
            cls._scale(radius.top_right if right_intact and top_intact else 0.0, scale),
            cls._scale(radius.bottom_right if right_intact and bottom_intact else 0.0, scale),
            cls._scale(radius.bottom_left if left_intact and bottom_intact else 0.0, scale),
        )
