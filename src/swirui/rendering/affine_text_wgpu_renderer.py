"""Affine shaped-text bridge for the retained native wgpu compositor.

Glyphon remains the fast path for ordinary text and positive uniform retained
scale. Text that needs rotation, shear, reflection, non-uniform scale or a
non-axis-aligned retained clip is shaped and rasterized by the same native
cosmic-text stack into a cached RGBA texture. The verified affine image pipeline
then owns transform, exact convex clipping and GPU presentation for that texture.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections import OrderedDict
from dataclasses import replace
from typing import Any

from swirui.window import Window

from .affine import Affine2D
from .affine_clip_wgpu_renderer import WgpuRenderer as _AffineClipWgpuRenderer
from .affine_wgpu_renderer import _DEFAULT_TEXT_COLOR, AffineScenePayload
from .geometry import Color
from .scene import ClipRegion, Scene, SceneNode, SceneNodeKind

_MAX_AFFINE_TEXT_CACHE_ENTRIES = 128
_MAX_AFFINE_TEXT_CACHE_BYTES = 64 * 1024 * 1024
_INTERNAL_TEXT_RESOURCE_PREFIX = "__swirui_affine_text_"


class WgpuRenderer(_AffineClipWgpuRenderer):
    """Persistent wgpu renderer with arbitrary-affine shaped-text composition."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._affine_text_cache: OrderedDict[str, int] = OrderedDict()
        self._affine_text_cache_bytes = 0

    @property
    def affine_text_cache_size(self) -> int:
        """Return retained native text textures used by arbitrary-affine scenes."""

        return len(self._affine_text_cache)

    @property
    def affine_text_cache_bytes(self) -> int:
        """Return CPU RGBA bytes retained for arbitrary-affine shaped text."""

        return self._affine_text_cache_bytes

    def _affine_scene_payload(self, window: Window, scene: Scene) -> AffineScenePayload:
        rasterize = getattr(self._native, "rasterize_text_rgba", None)
        if rasterize is None:
            # Older native wheels keep the previous explicit gate instead of
            # silently approximating unsupported text transforms or clips.
            return super()._affine_scene_payload(window, scene)

        replacements: dict[int, str] = {}
        frame_resources: set[str] = set()
        for node, _opacity, clips, world_transform in scene.walk_composited_affine():
            if node.kind is not SceneNodeKind.TEXT:
                continue
            if not node.text or node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
                continue
            if not self._requires_rasterized_text(node, clips, world_transform):
                continue
            resource_id = self._ensure_affine_text_resource(
                window,
                node,
                world_transform,
                rasterize,
            )
            replacements[id(node)] = resource_id
            frame_resources.add(resource_id)

        if not replacements:
            return super()._affine_scene_payload(window, scene)

        converted = self._scene_with_text_images(scene, replacements)
        self._trim_affine_text_cache(frame_resources)
        return super()._affine_scene_payload(window, converted)

    def _requires_rasterized_text(
        self,
        node: SceneNode,
        clips: tuple[ClipRegion, ...],
        world_transform: Affine2D,
    ) -> bool:
        if any(not transform.is_axis_aligned for transform, _bounds in clips):
            return True
        try:
            self._transformed_text_geometry(
                node.bounds,
                node.font_size,
                world_transform,
            )
        except RuntimeError:
            return True
        return False

    def _ensure_affine_text_resource(
        self,
        window: Window,
        node: SceneNode,
        world_transform: Affine2D,
        rasterize: Any,
    ) -> str:
        text = node.text
        if text is None:
            raise RuntimeError("Affine text rasterization requires text content.")
        fill = node.fill or _DEFAULT_TEXT_COLOR
        density = max(1.0, self._largest_linear_scale(world_transform))
        physical_width = node.bounds.width * window.scale * density
        physical_height = node.bounds.height * window.scale * density
        font_size = node.font_size * window.scale * density
        if not all(math.isfinite(value) for value in (physical_width, physical_height, font_size)):
            raise RuntimeError("Affine text raster geometry must remain finite.")
        width = max(1, math.ceil(physical_width))
        height = max(1, math.ceil(physical_height))
        resource_id = self._text_resource_id(
            text,
            node.font_family,
            width,
            height,
            font_size,
            fill,
        )

        if resource_id in self._affine_text_cache and resource_id in self._image_aliases:
            self._affine_text_cache.move_to_end(resource_id)
            return resource_id

        previous_size = self._affine_text_cache.pop(resource_id, None)
        if previous_size is not None:
            self._affine_text_cache_bytes -= previous_size
        rgba = bytes(
            rasterize(
                text,
                width,
                height,
                font_size,
                fill.r,
                fill.g,
                fill.b,
                fill.a,
                node.font_family,
            )
        )
        expected = width * height * 4
        if len(rgba) != expected:
            raise RuntimeError(
                "Native affine text rasterizer returned an invalid RGBA payload: "
                f"expected {expected} bytes, received {len(rgba)}."
            )
        self.register_image_rgba(resource_id, width, height, rgba)
        self._affine_text_cache[resource_id] = expected
        self._affine_text_cache_bytes += expected
        return resource_id

    def _trim_affine_text_cache(self, protected: set[str]) -> None:
        within_budget = (
            len(self._affine_text_cache) <= _MAX_AFFINE_TEXT_CACHE_ENTRIES
            and self._affine_text_cache_bytes <= _MAX_AFFINE_TEXT_CACHE_BYTES
        )
        if within_budget:
            return
        for resource_id in tuple(self._affine_text_cache):
            within_budget = (
                len(self._affine_text_cache) <= _MAX_AFFINE_TEXT_CACHE_ENTRIES
                and self._affine_text_cache_bytes <= _MAX_AFFINE_TEXT_CACHE_BYTES
            )
            if within_budget:
                break
            if resource_id in protected:
                continue
            removed_size = self._affine_text_cache.pop(resource_id)
            self._affine_text_cache_bytes -= removed_size
            self.unregister_image(resource_id)

    @staticmethod
    def _largest_linear_scale(transform: Affine2D) -> float:
        trace = (
            transform.m11 * transform.m11
            + transform.m12 * transform.m12
            + transform.m21 * transform.m21
            + transform.m22 * transform.m22
        )
        determinant = transform.determinant
        discriminant = max(0.0, trace * trace - 4.0 * determinant * determinant)
        return math.sqrt(0.5 * (trace + math.sqrt(discriminant)))

    @staticmethod
    def _text_resource_id(
        text: str,
        family: str,
        width: int,
        height: int,
        font_size: float,
        fill: Color,
    ) -> str:
        digest = hashlib.sha256()
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
        digest.update(family.encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            struct.pack(
                "!II5d",
                width,
                height,
                font_size,
                fill.r,
                fill.g,
                fill.b,
                fill.a,
            )
        )
        return f"{_INTERNAL_TEXT_RESOURCE_PREFIX}{digest.hexdigest()}"

    @classmethod
    def _scene_with_text_images(
        cls,
        scene: Scene,
        replacements: dict[int, str],
    ) -> Scene:
        def clone(node: SceneNode) -> SceneNode:
            children = [clone(child) for child in node.children]
            resource_id = replacements.get(id(node))
            if resource_id is None:
                return replace(node, children=children)
            return replace(
                node,
                kind=SceneNodeKind.IMAGE,
                fill=None,
                text=None,
                resource_id=resource_id,
                children=children,
            )

        return Scene(
            scene.width,
            scene.height,
            clone(scene.root),
            generation=scene.generation,
        )
