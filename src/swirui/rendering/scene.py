"""Scene graph primitives prepared for renderer backends."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from .geometry import Color, CornerRadius, Point, Rect


class SceneNodeKind(StrEnum):
    GROUP = "group"
    RECTANGLE = "rectangle"
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
    text: str | None = None
    font_size: float = 16.0
    font_family: str = "Segoe UI"
    resource_id: str | None = None
    children: list[SceneNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0.")
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

    def contains(self, target: SceneNode) -> bool:
        return any(node is target for node in self.walk())

    def hit_test(self, point: Point) -> SceneNode | None:
        """Return the visually topmost node under ``point``.

        Children with larger ``z_index`` values win. Equal z-index values use
        later insertion as the topmost visual, matching painter-style ordering.
        Transparent groups participate in the ancestry path but are not direct
        visual hit targets unless they have a fill.
        """

        path = self.hit_path(point)
        return path[-1] if path else None

    def hit_path(self, point: Point) -> tuple[SceneNode, ...]:
        """Return the ancestry path from this node to the topmost visual hit."""

        if self.opacity <= 0.0:
            return ()

        ordered_children = sorted(
            enumerate(self.children),
            key=lambda item: (item[1].z_index, item[0]),
            reverse=True,
        )
        for _, child in ordered_children:
            child_path = child.hit_path(point)
            if child_path:
                return (self, *child_path)

        if self.bounds.contains(point) and (
            self.kind is not SceneNodeKind.GROUP or self.fill is not None
        ):
            return (self,)
        return ()


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

    def hit_test(self, point: Point) -> SceneNode | None:
        return self.root.hit_test(point)

    def hit_path(self, point: Point) -> tuple[SceneNode, ...]:
        return self.root.hit_path(point)
