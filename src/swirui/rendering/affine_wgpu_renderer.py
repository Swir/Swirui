"""Affine-aware public wgpu renderer built on the verified retained compositor."""

from __future__ import annotations

import math
from typing import TypeAlias

from swirui.core import Component
from swirui.window import Window

from .affine import Affine2D
from .custom_wgpu_renderer import WgpuRenderer as _CustomWgpuRenderer
from .geometry import Color, CornerRadius, Point, Rect
from .scene import ClipRegion, Scene, SceneNodeKind
from .wgpu_renderer import ImageInstance, RectangleInstance, TextInstance

AffineShapeVertex: TypeAlias = tuple[float, ...]
AffineImageInstance: TypeAlias = tuple[
    str,
    float,
    float,
    float,
    float,
    float,
    tuple[float, float, float, float],
    tuple[float, float, float, float, float, float],
]
AffineScenePayload: TypeAlias = tuple[
    list[RectangleInstance],
    list[TextInstance],
    list[ImageInstance | AffineImageInstance],
    list[AffineShapeVertex],
]

_DEFAULT_TEXT_COLOR = Color(1.0, 1.0, 1.0, 1.0)
_ROUNDED_CORNER_SEGMENTS = 8


class WgpuRenderer(_CustomWgpuRenderer):
    """Persistent renderer with verified retained affine GPU-compositor slices.

    Non-affine scenes keep the existing mature renderer path unchanged. Scenes
    containing retained transforms use the exact ``walk_composited_affine``
    hierarchy. Arbitrary affine transforms are currently supported for filled
    ``Path2D`` geometry, solid/rounded rectangle fills and RGBA images through
    native GPU pipelines while preserving inherited opacity, HiDPI scaling,
    persistent native wgpu contexts and axis-aligned clipping.

    Shaped-text raster transforms remain deliberately gated until glyphon consumes
    the same affine contract. Transformed clip regions are accepted only when they
    remain axis-aligned; rotated/sheared clipping also stays gated rather than
    being approximated by a bounding box.
    """

    def render(self, window: Window, root: Component | None) -> None:
        scene = window.scene
        if scene is None or not scene.has_affine_transforms:
            super().render(window, root)
            return
        self._render_affine_scene(window)

    def _render_affine_scene(self, window: Window) -> None:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        self._surface_for(window)

        scene = window.scene
        if scene is None:
            return
        if any(node.kind is SceneNodeKind.BACKDROP_BLUR for node in scene.walk()):
            raise RuntimeError(
                "Affine SceneNode transforms with backdrop blur are not yet supported."
            )

        handle = window.native_handle.value
        context = self._contexts.get(handle)
        if context is None:
            raise RuntimeError(
                "Affine SceneNode GPU transforms require the persistent SwirUI native context."
            )

        self._context_scales[handle] = window.scale
        self._configure_scene_blur(context, window.scale)
        rectangles, texts, images, paths = self._affine_scene_payload(window, scene)
        background = self.background

        if images and getattr(context, "register_image_rgba", None) is None:
            raise RuntimeError(
                "Installed SwirUI native GPU core does not support image rendering."
            )

        if rectangles or texts or images or paths:
            draw = getattr(context, "draw_scene_with_paths", None)
            if draw is None:
                raise RuntimeError(
                    "Installed SwirUI native GPU core does not support affine path rendering."
                )
            rectangle_count, text_count, image_count, path_count = draw(
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
        else:
            context.clear(background.r, background.g, background.b, background.a)
            self.last_rectangle_count = 0
            self.last_text_count = 0
            self.last_image_count = 0
            self.last_path_count = 0

        self.last_backdrop_count = 0
        self._capture_adapter_info(context)
        self.frames_rendered += 1

    def _affine_scene_payload(self, window: Window, scene: Scene) -> AffineScenePayload:
        scale = window.scale
        rectangles: list[RectangleInstance] = []
        texts: list[TextInstance] = []
        images: list[ImageInstance | AffineImageInstance] = []
        paths: list[AffineShapeVertex] = []

        for node, effective_opacity, clips, world_transform in scene.walk_composited_affine():
            if node.kind is SceneNodeKind.BACKDROP_BLUR:
                raise RuntimeError(
                    "Affine SceneNode transforms with backdrop blur are not yet supported."
                )

            if node.kind in (SceneNodeKind.GROUP, SceneNodeKind.RECTANGLE):
                if node.fill is None:
                    continue
                if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                clip = self._resolved_affine_clip(scene, clips)
                visual_bounds = world_transform.transform_rect_bounds(node.bounds)
                if clip is None or visual_bounds.intersection(clip) is None:
                    continue

                rect_fill = node.fill
                radius = node.corner_radius
                clip_tuple = self._clip_tuple(clip, scale)
                if world_transform.is_identity:
                    rectangles.append(
                        (
                            self._scale(node.bounds.x, scale),
                            self._scale(node.bounds.y, scale),
                            self._scale(node.bounds.width, scale),
                            self._scale(node.bounds.height, scale),
                            rect_fill.r,
                            rect_fill.g,
                            rect_fill.b,
                            rect_fill.a * effective_opacity,
                            self._scale(radius.top_left, scale),
                            self._scale(radius.top_right, scale),
                            self._scale(radius.bottom_right, scale),
                            self._scale(radius.bottom_left, scale),
                            *clip_tuple,
                        )
                    )
                else:
                    self._append_affine_rectangle(
                        paths,
                        node.bounds,
                        radius,
                        rect_fill,
                        effective_opacity,
                        clip_tuple,
                        world_transform,
                        scale,
                    )
                continue

            if node.kind is SceneNodeKind.TEXT:
                self._require_identity_raster_transform(node.kind, world_transform)
                if not node.text or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                clip = self._resolved_affine_clip(scene, clips)
                if clip is None or node.bounds.intersection(clip) is None:
                    continue
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
                continue

            if node.kind is SceneNodeKind.IMAGE:
                if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                clip = self._resolved_affine_clip(scene, clips)
                visual_bounds = world_transform.transform_rect_bounds(node.bounds)
                if clip is None or visual_bounds.intersection(clip) is None:
                    continue
                resource_id = node.resource_id
                native_id = (
                    self._image_aliases.get(resource_id) if resource_id is not None else None
                )
                if native_id is None:
                    raise RuntimeError(
                        f"Scene image resource {resource_id!r} is not registered with WgpuRenderer."
                    )
                geometry: ImageInstance = (
                    native_id,
                    self._scale(node.bounds.x, scale),
                    self._scale(node.bounds.y, scale),
                    self._scale(node.bounds.width, scale),
                    self._scale(node.bounds.height, scale),
                    effective_opacity,
                    self._clip_tuple(clip, scale),
                )
                if world_transform.is_identity:
                    images.append(geometry)
                else:
                    affine_geometry: AffineImageInstance = (
                        *geometry,
                        self._physical_affine(world_transform, scale),
                    )
                    images.append(affine_geometry)
                continue

            if node.kind is not SceneNodeKind.PATH:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            clip = self._resolved_affine_clip(scene, clips)
            visual_bounds = world_transform.transform_rect_bounds(node.bounds)
            if clip is None or visual_bounds.intersection(clip) is None:
                continue
            path = node.path
            path_fill = node.fill
            if path is None or path_fill is None:
                continue

            clip_left, clip_top, clip_right, clip_bottom = self._clip_tuple(clip, scale)
            alpha = path_fill.a * effective_opacity
            transform = self._physical_affine(world_transform, scale)
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
                            *transform,
                        )
                    )

        return rectangles, texts, images, paths

    def _append_affine_rectangle(
        self,
        paths: list[AffineShapeVertex],
        bounds: Rect,
        radius: CornerRadius,
        fill: Color,
        effective_opacity: float,
        clip: tuple[float, float, float, float],
        transform: Affine2D,
        scale: float,
    ) -> None:
        outline = self._rounded_rectangle_outline(bounds, radius)
        if len(outline) < 3:
            return

        physical_transform = self._physical_affine(transform, scale)
        alpha = fill.a * effective_opacity
        anchor = outline[0]
        for index in range(1, len(outline) - 1):
            for point in (anchor, outline[index], outline[index + 1]):
                paths.append(
                    (
                        self._scale(point.x, scale),
                        self._scale(point.y, scale),
                        fill.r,
                        fill.g,
                        fill.b,
                        alpha,
                        *clip,
                        *physical_transform,
                    )
                )

    @staticmethod
    def _rounded_rectangle_outline(
        bounds: Rect,
        radius: CornerRadius,
    ) -> tuple[Point, ...]:
        max_radius = min(bounds.width, bounds.height) * 0.5
        radii = (
            min(radius.top_left, max_radius),
            min(radius.top_right, max_radius),
            min(radius.bottom_right, max_radius),
            min(radius.bottom_left, max_radius),
        )
        points: list[Point] = []

        def append_point(point: Point) -> None:
            if not points or points[-1] != point:
                points.append(point)

        def append_arc(
            center_x: float,
            center_y: float,
            corner_radius: float,
            start_angle: float,
        ) -> None:
            if corner_radius == 0.0:
                append_point(Point(center_x, center_y))
                return
            step = (math.pi * 0.5) / _ROUNDED_CORNER_SEGMENTS
            for segment in range(_ROUNDED_CORNER_SEGMENTS + 1):
                angle = start_angle + step * segment
                append_point(
                    Point(
                        center_x + math.cos(angle) * corner_radius,
                        center_y + math.sin(angle) * corner_radius,
                    )
                )

        top_left, top_right, bottom_right, bottom_left = radii
        append_arc(
            bounds.x + top_left,
            bounds.y + top_left,
            top_left,
            math.pi,
        )
        append_arc(
            bounds.right - top_right,
            bounds.y + top_right,
            top_right,
            math.pi * 1.5,
        )
        append_arc(
            bounds.right - bottom_right,
            bounds.bottom - bottom_right,
            bottom_right,
            0.0,
        )
        append_arc(
            bounds.x + bottom_left,
            bounds.bottom - bottom_left,
            bottom_left,
            math.pi * 0.5,
        )
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        return tuple(points)

    @staticmethod
    def _require_identity_raster_transform(
        kind: SceneNodeKind,
        transform: Affine2D,
    ) -> None:
        if not transform.is_identity:
            raise RuntimeError(
                f"Affine transforms for {kind.value} nodes require the native transform compositor."
            )

    @staticmethod
    def _resolved_affine_clip(scene: Scene, clips: tuple[ClipRegion, ...]) -> Rect | None:
        clip: Rect | None = Rect(0.0, 0.0, scene.width, scene.height)
        for transform, bounds in clips:
            if not transform.is_axis_aligned:
                raise RuntimeError(
                    "Rotated or sheared SceneNode clipping requires the native "
                    "transform compositor."
                )
            transformed = transform.transform_rect_bounds(bounds)
            clip = transformed if clip is None else clip.intersection(transformed)
            if clip is None:
                return None
        return clip

    @staticmethod
    def _physical_affine(
        transform: Affine2D,
        scale: float,
    ) -> tuple[float, float, float, float, float, float]:
        return (
            transform.m11,
            transform.m12,
            transform.m21,
            transform.m22,
            transform.tx * scale,
            transform.ty * scale,
        )
