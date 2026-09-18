"""Scene graph primitives prepared for renderer backends."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from .affine import Affine2D
from .geometry import Color, CornerRadius, Path2D, Point, Rect

_MAX_BACKDROP_BLUR_RADIUS = 64.0
_IDENTITY_TRANSFORM = Affine2D()
ClipRegion = tuple[Affine2D, Rect]


def _compose_transform(local: Affine2D, parent: Affine2D) -> Affine2D:
    """Compose retained transforms without allocating on the identity hot path."""

    if local.is_identity:
        return parent
    if parent.is_identity:
        return local
    return local.then(parent)


class SceneNodeKind(StrEnum):
    GROUP = "group"
    RECTANGLE = "rectangle"
    PATH = "path"
    TEXT = "text"
    IMAGE = "image"
    BACKDROP_BLUR = "backdrop_blur"


@dataclass(slots=True)
class SceneNode:
    """A render-backend friendly node in the prepared scene graph.

    ``transform`` maps authored logical-DIP coordinates into visual coordinates.
    Hit testing composes ancestor and descendant affine transforms before mapping
    the pointer back into each node's authored coordinates. Raster composition
    intentionally rejects transformed nodes until every primitive, shaped text
    and clipping path share one verified renderer contract; this prevents partial
    rotation support from silently diverging from input.
    """

    key: str
    kind: SceneNodeKind
    bounds: Rect
    opacity: float = 1.0
    z_index: int = 0
    fill: Color | None = None
    corner_radius: CornerRadius = field(default_factory=CornerRadius)
    path: Path2D | None = None
    text: str | None = None
    font_size: float = 16.0
    font_family: str = "Segoe UI"
    resource_id: str | None = None
    children: list[SceneNode] = field(default_factory=list)
    clip_to_bounds: bool = False
    hit_testable: bool = True
    blur_radius: float = 0.0
    transform: Affine2D = field(default_factory=Affine2D)

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0.")
        if self.kind is SceneNodeKind.PATH:
            if self.path is None:
                raise ValueError("Path scene nodes require Path2D geometry.")
            if self.fill is None:
                raise ValueError("Path scene nodes require a fill color.")
        if self.kind is SceneNodeKind.TEXT:
            if self.text is None:
                raise ValueError("Text scene nodes require text content.")
            if self.font_size <= 0:
                raise ValueError("Text scene nodes require a positive font_size.")
            if not self.font_family:
                raise ValueError("Text scene nodes require a font_family.")
        if self.kind is SceneNodeKind.IMAGE and self.resource_id is None:
            raise ValueError("Image scene nodes require a resource_id.")
        if self.kind is SceneNodeKind.BACKDROP_BLUR:
            if not math.isfinite(self.blur_radius):
                raise ValueError("Backdrop blur radius must be finite.")
            if not 0.0 < self.blur_radius <= _MAX_BACKDROP_BLUR_RADIUS:
                raise ValueError(
                    f"Backdrop blur radius must be in the range (0, {_MAX_BACKDROP_BLUR_RADIUS}]."
                )
            if self.bounds.width <= 0.0 or self.bounds.height <= 0.0:
                raise ValueError("Backdrop blur bounds must have positive dimensions.")

    @property
    def visual_bounds(self) -> Rect:
        """Return the axis-aligned visual bounds after this node's own transform."""

        if self.transform.is_identity:
            return self.bounds
        return self.transform.transform_rect_bounds(self.bounds)

    def add(self, *children: SceneNode) -> SceneNode:
        for child in children:
            if child is self or child.contains(self):
                raise ValueError("Adding this node would create a scene-graph cycle.")
            if child not in self.children:
                self.children.append(child)
        return self

    def walk(self) -> Iterator[SceneNode]:
        yield self
        for child in sorted(self.children, key=lambda item: item.z_index):
            yield from child.walk()

    def walk_with_opacity(
        self,
        inherited_opacity: float = 1.0,
    ) -> Iterator[tuple[SceneNode, float]]:
        """Yield painter-ordered nodes with opacity inherited from all ancestors."""

        for node, opacity, _clip in self.walk_composited(inherited_opacity, None):
            yield node, opacity

    def walk_composited(
        self,
        inherited_opacity: float = 1.0,
        inherited_clip: Rect | None = None,
    ) -> Iterator[tuple[SceneNode, float, Rect | None]]:
        """Yield painter-ordered nodes with cumulative opacity and rectangular clip.

        ``clip_to_bounds`` intersects this node's bounds with the inherited clip
        and applies the result to the node and its full subtree. Empty clipped
        subtrees are discarded before renderer resource preparation. A ``None``
        clip means no ancestor has requested clipping.

        Affine transforms are deliberately blocked from raster composition here
        until the native renderer can apply one transform coherently to rounded
        rectangles, paths, images, shaped text and rotated clipping. Hit testing
        can evolve first without ever displaying geometry at a different position
        from the pointer target.
        """

        if not self.transform.is_identity:
            raise RuntimeError(
                "Affine SceneNode raster transforms require the native transform compositor."
            )

        effective_opacity = inherited_opacity * self.opacity
        if effective_opacity <= 0.0:
            return

        effective_clip = inherited_clip
        if self.clip_to_bounds:
            effective_clip = (
                self.bounds
                if inherited_clip is None
                else inherited_clip.intersection(self.bounds)
            )
            if effective_clip is None:
                return

        yield self, effective_opacity, effective_clip
        for child in sorted(self.children, key=lambda item: item.z_index):
            yield from child.walk_composited(effective_opacity, effective_clip)

    def contains(self, target: SceneNode) -> bool:
        return any(node is target for node in self.walk())

    def hit_test(self, point: Point) -> SceneNode | None:
        """Return the visually topmost node under ``point``.

        Children with larger ``z_index`` values win. Equal z-index values use
        later insertion as the topmost visual, matching painter-style ordering.
        Transparent groups participate in the ancestry path but are not direct
        visual hit targets unless they have a fill. Decorative nodes can opt out
        of direct hit testing with ``hit_testable=False`` while their descendants
        remain independently eligible.

        Affine transforms are composed from the current node through its ancestors
        before hit testing. This keeps descendants aligned with transformed parent
        containers and preserves exact transformed clipping rather than reducing a
        rotated clip to its axis-aligned visual bounds.
        """

        path = self.hit_path(point)
        return path[-1] if path else None

    def hit_path(self, point: Point) -> tuple[SceneNode, ...]:
        """Return the ancestry path from this node to the topmost visual hit."""

        return self._hit_path(point, _IDENTITY_TRANSFORM, ())

    def _hit_path(
        self,
        point: Point,
        parent_transform: Affine2D,
        inherited_clips: tuple[ClipRegion, ...],
    ) -> tuple[SceneNode, ...]:
        if self.opacity <= 0.0:
            return ()
        if not self._point_within_clips(point, inherited_clips):
            return ()

        world_transform = _compose_transform(self.transform, parent_transform)
        effective_clips = inherited_clips
        if self.clip_to_bounds:
            if not self._transformed_bounds_contains(point, world_transform):
                return ()
            effective_clips = (*inherited_clips, (world_transform, self.bounds))

        candidates = (
            (index, child)
            for index, child in enumerate(self.children)
            if child._subtree_may_hit(point, world_transform)
        )
        ordered_children = sorted(
            candidates,
            key=lambda item: (item[1].z_index, item[0]),
            reverse=True,
        )
        for _, child in ordered_children:
            child_path = child._hit_path(point, world_transform, effective_clips)
            if child_path:
                return (self, *child_path)

        if self._contains_visual_point(point, world_transform):
            return (self,)
        return ()

    def _subtree_may_hit(
        self,
        point: Point,
        parent_transform: Affine2D = _IDENTITY_TRANSFORM,
    ) -> bool:
        """Reject a subtree only when it is impossible for it to hit ``point``.

        The caller has already verified every inherited clip for this pointer, so
        the broad phase only evaluates this subtree's composed visual bounds. Leaf
        visuals can be rejected immediately; unclipped containers with descendants
        remain eligible outside their own bounds because descendants may overflow.
        """

        if self.opacity <= 0.0:
            return False
        world_transform = _compose_transform(self.transform, parent_transform)
        if self._transformed_bounds_contains(point, world_transform):
            return True
        if self.clip_to_bounds:
            return False
        return bool(self.children)

    def _contains_visual_point(
        self,
        point: Point,
        world_transform: Affine2D = _IDENTITY_TRANSFORM,
    ) -> bool:
        if not self.hit_testable:
            return False
        authored = self._authored_point(point, world_transform)
        if not self.bounds.contains(authored):
            return False
        if self.kind in (SceneNodeKind.GROUP, SceneNodeKind.BACKDROP_BLUR):
            return self.fill is not None
        if self.kind is SceneNodeKind.PATH:
            path = self.path
            if path is None:
                return False
            local = Point(authored.x - self.bounds.x, authored.y - self.bounds.y)
            return path.contains(local)
        return True

    def _transformed_bounds_contains(
        self,
        point: Point,
        world_transform: Affine2D = _IDENTITY_TRANSFORM,
    ) -> bool:
        return self.bounds.contains(self._authored_point(point, world_transform))

    @staticmethod
    def _point_within_clips(point: Point, clips: tuple[ClipRegion, ...]) -> bool:
        for transform, bounds in clips:
            authored = (
                point
                if transform.is_identity
                else transform.inverse().transform_point(point)
            )
            if not bounds.contains(authored):
                return False
        return True

    @staticmethod
    def _authored_point(point: Point, world_transform: Affine2D) -> Point:
        if world_transform.is_identity:
            return point
        return world_transform.inverse().transform_point(point)


@dataclass(slots=True)
class Scene:
    """Prepared scene submitted to a renderer for a single window."""

    width: float
    height: float
    root: SceneNode
    generation: int = 0

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Scene dimensions cannot be negative.")

    @property
    def has_affine_transforms(self) -> bool:
        """Return whether any retained node carries a non-identity affine transform."""

        return any(not node.transform.is_identity for node in self.walk())

    def touch(self) -> None:
        self.generation += 1

    def walk(self) -> Iterator[SceneNode]:
        yield from self.root.walk()

    def walk_with_opacity(self) -> Iterator[tuple[SceneNode, float]]:
        """Yield painter-ordered nodes with cumulative scene opacity."""

        yield from self.root.walk_with_opacity()

    def walk_composited(self) -> Iterator[tuple[SceneNode, float, Rect | None]]:
        """Yield painter-ordered nodes with cumulative opacity and clip bounds."""

        yield from self.root.walk_composited()

    def hit_test(self, point: Point) -> SceneNode | None:
        return self.root.hit_test(point)

    def hit_path(self, point: Point) -> tuple[SceneNode, ...]:
        return self.root.hit_path(point)

    def hit_test_xy(self, x: float, y: float) -> SceneNode | None:
        """Coordinate helper used by native pointer-event routing."""

        return self.hit_test(Point(x, y))

    def hit_path_xy(self, x: float, y: float) -> tuple[SceneNode, ...]:
        """Coordinate helper that avoids renderer imports in platform/window code."""

        return self.hit_path(Point(x, y))
