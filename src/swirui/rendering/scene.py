"""Scene graph primitives prepared for renderer backends."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from .geometry import Color, CornerRadius, Path2D, Point, Rect


class SceneNodeKind(StrEnum):
    GROUP = "group"
    RECTANGLE = "rectangle"
    PATH = "path"
    TEXT = "text"
    IMAGE = "image"


@dataclass(slots=True)
class SceneNode:
    """A render-backend friendly node in the prepared scene graph."""

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
        """

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
        """

        path = self.hit_path(point)
        return path[-1] if path else None

    def hit_path(self, point: Point) -> tuple[SceneNode, ...]:
        """Return the ancestry path from this node to the topmost visual hit."""

        if self.opacity <= 0.0:
            return ()
        if self.clip_to_bounds and not self.bounds.contains(point):
            return ()

        candidates = (
            (index, child)
            for index, child in enumerate(self.children)
            if child._subtree_may_hit(point)
        )
        ordered_children = sorted(
            candidates,
            key=lambda item: (item[1].z_index, item[0]),
            reverse=True,
        )
        for _, child in ordered_children:
            child_path = child.hit_path(point)
            if child_path:
                return (self, *child_path)

        if self._contains_visual_point(point):
            return (self,)
        return ()

    def _subtree_may_hit(self, point: Point) -> bool:
        """Reject a subtree only when it is impossible for it to hit ``point``.

        Leaf visuals cannot hit outside their own bounds, so broad-phase culling
        can remove them before z-order sorting. Containers with descendants stay
        eligible outside their bounds unless clipping is enabled because SwirUI
        permits descendants to paint and receive input beyond an unclipped parent.
        """

        if self.opacity <= 0.0:
            return False
        if self.bounds.contains(point):
            return True
        if self.clip_to_bounds:
            return False
        return bool(self.children)

    def _contains_visual_point(self, point: Point) -> bool:
        if not self.hit_testable or not self.bounds.contains(point):
            return False
        if self.kind is SceneNodeKind.GROUP:
            return self.fill is not None
        if self.kind is SceneNodeKind.PATH:
            path = self.path
            if path is None:
                return False
            local = Point(point.x - self.bounds.x, point.y - self.bounds.y)
            return path.contains(local)
        return True


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
