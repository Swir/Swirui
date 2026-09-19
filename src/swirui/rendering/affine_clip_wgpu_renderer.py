"""Affine wgpu renderer with exact rotated/sheared geometry clipping.

This layer keeps the mature affine renderer fast path untouched for ordinary
axis-aligned clips.  When retained geometry enters a rotated or sheared
``clip_to_bounds`` hierarchy, triangles are transformed to world space and
clipped exactly against the transformed convex quads before native submission.
Images and shaped text keep their existing explicit non-axis clip gate until
those pipelines gain equivalent texture/glyph clipping support.
"""

from __future__ import annotations

from .affine import Affine2D
from .affine_clipping import (
    ConvexPolygon,
    clip_triangle_to_convex_polygons,
    transformed_rect_polygon,
    triangulate_convex_polygon,
)
from .affine_wgpu_renderer import (
    AffineImageInstance,
    AffineScenePayload,
    AffineShapeVertex,
    WgpuRenderer as _BaseAffineWgpuRenderer,
    _DEFAULT_TEXT_COLOR,
)
from .geometry import Color, Point, Rect
from .scene import ClipRegion, Scene, SceneNodeKind
from .wgpu_renderer import ImageInstance, RectangleInstance, TextInstance

_IDENTITY_GPU_AFFINE = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


class WgpuRenderer(_BaseAffineWgpuRenderer):
    """Persistent affine renderer with exact convex clips for filled geometry."""

    def _affine_scene_payload(self, window: object, scene: Scene) -> AffineScenePayload:
        if not self._scene_has_non_axis_clip(scene):
            return super()._affine_scene_payload(window, scene)  # type: ignore[arg-type]

        scale = float(window.scale)  # type: ignore[attr-defined]
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
                axis_clip, convex_clips = self._resolved_geometry_clips(scene, clips)
                visual_bounds = world_transform.transform_rect_bounds(node.bounds)
                if axis_clip is None or visual_bounds.intersection(axis_clip) is None:
                    continue

                fill = node.fill
                radius = node.corner_radius
                clip_tuple = self._clip_tuple(axis_clip, scale)
                if not convex_clips and world_transform.is_identity:
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
                            *clip_tuple,
                        )
                    )
                elif convex_clips:
                    outline = self._rounded_rectangle_outline(node.bounds, radius)
                    self._append_exact_clipped_fan(
                        paths,
                        outline,
                        fill,
                        effective_opacity,
                        clip_tuple,
                        convex_clips,
                        world_transform,
                        scale,
                    )
                else:
                    self._append_affine_rectangle(
                        paths,
                        node.bounds,
                        radius,
                        fill,
                        effective_opacity,
                        clip_tuple,
                        world_transform,
                        scale,
                    )
                continue

            if node.kind is SceneNodeKind.TEXT:
                if not node.text or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                text_bounds, transformed_font_size = self._transformed_text_geometry(
                    node.bounds,
                    node.font_size,
                    world_transform,
                )
                clip = self._resolved_affine_clip(scene, clips)
                if clip is None or text_bounds.intersection(clip) is None:
                    continue
                text_fill = node.fill or _DEFAULT_TEXT_COLOR
                texts.append(
                    (
                        node.text,
                        self._scale(text_bounds.x, scale),
                        self._scale(text_bounds.y, scale),
                        self._scale(text_bounds.width, scale),
                        self._scale(text_bounds.height, scale),
                        self._scale(transformed_font_size, scale),
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
                    images.append((*geometry, self._physical_affine(world_transform, scale)))
                continue

            if node.kind is not SceneNodeKind.PATH:
                continue
            if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            axis_clip, convex_clips = self._resolved_geometry_clips(scene, clips)
            visual_bounds = world_transform.transform_rect_bounds(node.bounds)
            if axis_clip is None or visual_bounds.intersection(axis_clip) is None:
                continue
            path = node.path
            path_fill = node.fill
            if path is None or path_fill is None:
                continue

            clip_tuple = self._clip_tuple(axis_clip, scale)
            if convex_clips:
                for triangle in path.triangulate():
                    authored = tuple(
                        Point(node.bounds.x + point.x, node.bounds.y + point.y)
                        for point in triangle
                    )
                    self._append_exact_clipped_triangle(
                        paths,
                        authored,  # type: ignore[arg-type]
                        path_fill,
                        effective_opacity,
                        clip_tuple,
                        convex_clips,
                        world_transform,
                        scale,
                    )
            else:
                clip_left, clip_top, clip_right, clip_bottom = clip_tuple
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

    @staticmethod
    def _scene_has_non_axis_clip(scene: Scene) -> bool:
        return any(
            any(not transform.is_axis_aligned for transform, _bounds in clips)
            for _node, _opacity, clips, _world_transform in scene.walk_composited_affine()
        )

    @staticmethod
    def _resolved_geometry_clips(
        scene: Scene,
        clips: tuple[ClipRegion, ...],
    ) -> tuple[Rect | None, tuple[ConvexPolygon, ...]]:
        axis_clip: Rect | None = Rect(0.0, 0.0, scene.width, scene.height)
        convex_clips: list[ConvexPolygon] = []
        for transform, bounds in clips:
            if transform.is_axis_aligned:
                transformed = transform.transform_rect_bounds(bounds)
                axis_clip = (
                    transformed if axis_clip is None else axis_clip.intersection(transformed)
                )
                if axis_clip is None:
                    return None, ()
            else:
                convex_clips.append(transformed_rect_polygon(transform, bounds))
        return axis_clip, tuple(convex_clips)

    def _append_exact_clipped_fan(
        self,
        paths: list[AffineShapeVertex],
        outline: tuple[Point, ...],
        fill: Color,
        effective_opacity: float,
        axis_clip: tuple[float, float, float, float],
        convex_clips: tuple[ConvexPolygon, ...],
        world_transform: Affine2D,
        scale: float,
    ) -> None:
        if len(outline) < 3:
            return
        anchor = outline[0]
        for index in range(1, len(outline) - 1):
            self._append_exact_clipped_triangle(
                paths,
                (anchor, outline[index], outline[index + 1]),
                fill,
                effective_opacity,
                axis_clip,
                convex_clips,
                world_transform,
                scale,
            )

    def _append_exact_clipped_triangle(
        self,
        paths: list[AffineShapeVertex],
        triangle: tuple[Point, Point, Point],
        fill: Color,
        effective_opacity: float,
        axis_clip: tuple[float, float, float, float],
        convex_clips: tuple[ConvexPolygon, ...],
        world_transform: Affine2D,
        scale: float,
    ) -> None:
        world_triangle = tuple(world_transform.transform_point(point) for point in triangle)
        polygon = clip_triangle_to_convex_polygons(
            world_triangle,  # type: ignore[arg-type]
            convex_clips,
        )
        alpha = fill.a * effective_opacity
        for clipped_triangle in triangulate_convex_polygon(polygon):
            for point in clipped_triangle:
                paths.append(
                    (
                        self._scale(point.x, scale),
                        self._scale(point.y, scale),
                        fill.r,
                        fill.g,
                        fill.b,
                        alpha,
                        *axis_clip,
                        *_IDENTITY_GPU_AFFINE,
                    )
                )
