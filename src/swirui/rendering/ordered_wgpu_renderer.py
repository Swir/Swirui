"""Preserve retained painter order across native primitive batch types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from swirui.core import Component
from swirui.window import Window

from .affine_text_wgpu_renderer import WgpuRenderer as _AffineTextRenderer
from .backdrop_wgpu_renderer import BackdropRegion
from .scene import Scene, SceneNodeKind
from .wgpu_renderer import ImageInstance, RectangleInstance, ShapeVertex, TextInstance

OrderedPayload = tuple[
    list[list[RectangleInstance]],
    list[list[TextInstance]],
    list[list[ImageInstance]],
    list[list[ShapeVertex]],
    list[BackdropRegion | None],
]
_RANK = {
    SceneNodeKind.GROUP: 0,
    SceneNodeKind.RECTANGLE: 0,
    SceneNodeKind.PATH: 1,
    SceneNodeKind.IMAGE: 2,
    SceneNodeKind.TEXT: 3,
}


@dataclass(slots=True)
class _OrderedEntry:
    scene: Scene
    generation: int
    scale: float
    aliases: tuple[tuple[str, str], ...]
    payload: OrderedPayload | None
    token: int


class WgpuRenderer(_AffineTextRenderer):
    """Split batches only when their fixed primitive order would change the scene.

    The native batch paints rectangles, paths, images and text in that order.
    A later rectangle must therefore start a fresh segment after a path/image/text.
    None boundaries preserve the offscreen target without blurring it; actual
    backdrop boundaries still composite glass. Unchanged frames reuse native output.

    Older native modules and affine scenes retain their established rendering path.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ordered_cache: dict[int, _OrderedEntry] = {}

    def render(self, window: Window, root: Component | None) -> None:
        scene = window.scene
        if scene is None or scene.has_affine_transforms:
            super().render(window, root)
            return
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        self._surface_for(window)
        handle = window.native_handle.value
        context = self._contexts.get(handle)
        draw = getattr(context, "draw_scene_ordered_cached", None)
        if draw is None:
            super().render(window, root)
            return
        entry = self._ordered_payload(window, scene)
        if entry.payload is None:
            super().render(window, root)
            return
        self._context_scales[handle] = window.scale
        self._configure_scene_blur(context, window.scale)
        background = self.background
        counts = draw(
            *entry.payload, entry.token, background.r, background.g, background.b, background.a
        )
        (
            self.last_rectangle_count,
            self.last_text_count,
            self.last_image_count,
            self.last_path_count,
            self.last_backdrop_count,
        ) = map(int, counts)
        self._capture_adapter_info(context)
        self.frames_rendered += 1

    def destroy_surface(self, window: Window) -> None:
        self._ordered_cache.pop(id(window), None)
        super().destroy_surface(window)

    def shutdown(self) -> None:
        self._ordered_cache.clear()
        super().shutdown()

    def _ordered_payload(self, window: Window, scene: Scene) -> _OrderedEntry:
        aliases = tuple(sorted(self._image_aliases.items()))
        cached = self._ordered_cache.get(id(window))
        if (
            cached is not None
            and cached.scene is scene
            and cached.generation == scene.generation
            and cached.scale == window.scale
            and cached.aliases == aliases
        ):
            return cached
        rectangles: list[list[RectangleInstance]] = [[]]
        texts: list[list[TextInstance]] = [[]]
        images: list[list[ImageInstance]] = [[]]
        paths: list[list[ShapeVertex]] = [[]]
        boundaries: list[BackdropRegion | None] = []
        previous_rank = -1
        needs_ordering = False

        def split(boundary: BackdropRegion | None) -> None:
            boundaries.append(boundary)
            rectangles.append([])
            texts.append([])
            images.append([])
            paths.append([])

        for node, opacity, inherited_clip in scene.walk_composited():
            clip = self._visible_clip(scene.width, scene.height, inherited_clip)
            if clip is None or node.bounds.intersection(clip) is None:
                continue
            if node.kind is SceneNodeKind.BACKDROP_BLUR:
                visible = node.bounds.intersection(clip)
                assert visible is not None
                split(self._backdrop_region(node, visible, window.scale))
                previous_rank = -1
                continue
            if node.kind in (SceneNodeKind.RECTANGLE, SceneNodeKind.GROUP) and node.fill is None:
                continue
            rank = _RANK[node.kind]
            if rank < previous_rank:
                split(None)
                needs_ordering = True
            previous_rank = rank
            self._append_node(
                node,
                opacity,
                inherited_clip,
                scene.width,
                scene.height,
                window.scale,
                rectangles[-1],
                texts[-1],
                images[-1],
                paths[-1],
            )
        payload = (rectangles, texts, images, paths, boundaries) if needs_ordering else None
        entry = _OrderedEntry(
            scene,
            scene.generation,
            window.scale,
            aliases,
            payload,
            self._allocate_native_effect_token(),
        )
        self._ordered_cache[id(window)] = entry
        return entry
