"""Affine-aware public wgpu renderer built on the verified retained compositor."""

from __future__ import annotations

from typing import TypeAlias

from swirui.core import Component
from swirui.window import Window

from .affine import Affine2D
from .custom_wgpu_renderer import WgpuRenderer as _CustomWgpuRenderer
from .geometry import Color, Rect
from .scene import ClipRegion, Scene, SceneNodeKind
from .wgpu_renderer import ImageInstance, RectangleInstance, TextInstance

AffineShapeVertex: TypeAlias = tuple[float, ...]
AffineScenePayload: TypeAlias = tuple[
    list[RectangleInstance],
    list[TextInstance],
    list[ImageInstance],
    list[AffineShapeVertex],
]

_DEFAULT_TEXT_COLOR = Color(1.0, 1.0, 1.0, 1.0)


class WgpuRenderer(_CustomWgpuRenderer):
    """Persistent renderer with the first native affine GPU-compositor slice.

    Non-affine scenes keep the existing mature renderer path unchanged. Scenes
    containing retained transforms use the exact ``walk_composited_affine``
    hierarchy. This first GPU slice supports arbitrary affine transforms for
    filled ``Path2D`` geometry while preserving inherited opacity, HiDPI scaling,
    painter ordering inside the existing primitive batches and persistent native
    wgpu contexts.

    Rectangle, shaped-text and image raster transforms remain deliberately gated
    until their native pipelines consume the same affine contract. Transformed
    clip regions are accepted only when they remain axis-aligned; rotated/sheared
    clipping also stays gated rather than being approximated by a bounding box.
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
        images: list[ImageInstance] = []
        paths: list[AffineShapeVertex] = []

        for node, effective_opacity, clips, world_transform in scene.walk_composited_affine():
            if node.kind is SceneNodeKind.BACKDROP_BLUR:
                raise RuntimeError(
                    "Affine SceneNode transforms with backdrop blur are not yet supported."
                )

            if node.kind in (SceneNodeKind.GROUP, SceneNodeKind.RECTANGLE):
                if node.fill is None:
                    continue
                self._require_identity_raster_transform(node.kind, world_transform)
                if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                clip = self._resolved_affine_clip(scene, clips)
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
                continue

            if node.kind is SceneNodeKind.TEXT:
                self._require_identity_raster_transform(node.kind, world_transform)
                if not node.text or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                clip = self._resolved_affine_clip(scene, clips)
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
                continue

            if node.kind is SceneNodeKind.IMAGE:
                self._require_identity_raster_transform(node.kind, world_transform)
                if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                    continue
                clip = self._resolved_affine_clip(scene, clips)
                if clip is None or node.bounds.intersection(clip) is None:
                    continue
                resource_id = node.resource_id
                native_id = (
                    self._image_aliases.get(resource_id) if resource_id is not None else None
                )
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
            fill = node.fill
            if path is None or fill is None:
                continue

            clip_left, clip_top, clip_right, clip_bottom = self._clip_tuple(clip, scale)
            alpha = fill.a * effective_opacity
            transform = self._physical_affine(world_transform, scale)
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
                            *transform,
                        )
                    )

        return rectangles, texts, images, paths

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
    def _physical_affine(transform: Affine2D, scale: float) -> tuple[float, ...]:
        return (
            transform.m11,
            transform.m12,
            transform.m21,
            transform.m22,
            transform.tx * scale,
            transform.ty * scale,
        )
