"""Backdrop-aware extension of the persistent Rust/wgpu renderer bridge."""

from __future__ import annotations

from typing import Any

from swirui.core import Component, PresentationMode
from swirui.window import Window

from .geometry import Color, Rect
from .scene import SceneNode, SceneNodeKind
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


class WgpuRenderer(_BaseWgpuRenderer):
    """Persistent GPU renderer with painter-order backdrop blur boundaries.

    Backdrop nodes split a retained scene into ordered segments. Each segment is
    submitted into the same persistent offscreen target, the already-painted
    backdrop is blurred and composited into the requested rounded region, and
    later segments are then drawn sharp on top. Scenes without backdrop nodes
    stay on the existing fast path without extra segmentation or GPU passes.
    """

    def __init__(
        self,
        *,
        background: Color | None = None,
        native_module: Any | None = None,
        presentation_mode: PresentationMode = PresentationMode.AUTO_VSYNC,
        maximum_frame_latency: int = 1,
        scene_blur_radius: float = 0.0,
    ) -> None:
        super().__init__(
            background=background,
            native_module=native_module,
            presentation_mode=presentation_mode,
            maximum_frame_latency=maximum_frame_latency,
            scene_blur_radius=scene_blur_radius,
        )
        self.last_backdrop_count = 0

    def render(self, window: Window, root: Component | None) -> None:
        payload = self._backdrop_payload(window)
        if payload is None:
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

    def _backdrop_payload(self, window: Window) -> BackdropPayload | None:
        scene = window.scene
        if scene is None:
            return None
        records = list(scene.walk_composited())
        if not any(node.kind is SceneNodeKind.BACKDROP_BLUR for node, _, _ in records):
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

        if not backdrops:
            return None
        return (
            rectangle_segments,
            text_segments,
            image_segments,
            path_segments,
            backdrops,
        )

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
            return

        if node.kind is SceneNodeKind.TEXT:
            if not node.text or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                return
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
            fill = node.fill
            if (
                path is None
                or fill is None
                or node.bounds.width <= 0.0
                or node.bounds.height <= 0.0
            ):
                return
            clip_left, clip_top, clip_right, clip_bottom = self._clip_tuple(clip, scale)
            alpha = fill.a * effective_opacity
            for triangle in path.triangulate():
                for point in triangle:
                    paths.append(
                        (
                            self._scale(node.bounds.x + point.x, scale),
                            self._scale(node.bounds.y + point.y, scale),
                            fill.r,
                            fill.g,
                            fill.b,
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
